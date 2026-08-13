from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from pathlib import Path
import shutil

from excel_reader import read_tv_excel
from analytics import calculate_analytics
from charts import create_all_charts


app = FastAPI(
    title="TV Analytics API",
    description="Hindi and English TV Channel Analytics",
)


BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "output"
HINDI_OUTPUT = OUTPUT_FOLDER / "hindi"
ENGLISH_OUTPUT = OUTPUT_FOLDER / "english"

for folder in [
    UPLOAD_FOLDER,
    OUTPUT_FOLDER,
    HINDI_OUTPUT,
    ENGLISH_OUTPUT,
]:
    folder.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>TV Analytics API</title>
    </head>
    <body>
        <h1>TV Analytics API</h1>
        <p>API is running successfully.</p>
        <p><a href="/docs">Open API documentation</a></p>
    </body>
    </html>
    """


def _save_upload(file: UploadFile):
    if not file.filename:
        raise ValueError("No file was uploaded.")

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise ValueError("Please upload an Excel file (.xlsx or .xls).")

    save_path = UPLOAD_FOLDER / Path(file.filename).name

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return save_path


def _detect_language(extracted, filename):
    """
    Detect Hindi vs English using the actual channel names.
    Falls back to filename if needed.
    """
    text = " ".join(
        str(x)
        for x in extracted.get("youtube_columns", [])
    ).lower()

    hindi_terms = [
        "aaj tak",
        "india tv",
        "republic bharat",
        "tv 9 bharatvarsh",
        "times now navbharat",
        "ndtv india",
        "news 18 india",
        "abp news",
        "zee news",
        "news24",
    ]

    if any(term in text for term in hindi_terms):
        return "hindi"

    filename_text = str(filename).lower()

    if "hindi" in filename_text:
        return "hindi"

    return "english"


@app.post("/upload-test")
async def upload_test(file: UploadFile = File(...)):
    try:
        save_path = _save_upload(file)
        return {
            "status": "success",
            "message": "Excel uploaded successfully.",
            "filename": file.filename,
            "saved_to": str(save_path),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.post("/inspect")
async def inspect_excel(file: UploadFile = File(...)):
    try:
        save_path = _save_upload(file)
        result = read_tv_excel(save_path)

        return {
            "status": "success",
            "filename": file.filename,
            "language": _detect_language(result, file.filename),
            "rows": result["total_rows"],
            "latest_year": result["latest_year"],
            "latest_week": result["latest_week"],
            "base_columns": result["base_columns"],
            "youtube_columns": result["youtube_columns"],
            "youtube_column_count": len(result["youtube_columns"]),
            "nct_columns": result["nct_columns"],
            "nct_column_count": len(result["nct_columns"]),
        }

    except Exception as e:
        return {
            "status": "error",
            "stage": "excel_extraction",
            "message": str(e),
        }


@app.post("/analyze")
async def analyze_excel(file: UploadFile = File(...)):
    try:
        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------
        save_path = _save_upload(file)

        # ----------------------------------------------------
        # READ EXCEL
        # ----------------------------------------------------
        extracted = read_tv_excel(save_path)

        df = extracted["data"]
        youtube_columns = extracted["youtube_columns"]
        nct_columns = extracted["nct_columns"]

    except Exception as e:
        return {
            "status": "error",
            "stage": "excel_extraction",
            "message": str(e),
        }

    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------
    language = _detect_language(
        extracted,
        file.filename,
    )

    output_root = (
        HINDI_OUTPUT
        if language == "hindi"
        else ENGLISH_OUTPUT
    )

    # --------------------------------------------------------
    # ANALYTICS
    # --------------------------------------------------------
    try:
        results = calculate_analytics(
            df=df,
            youtube_columns=youtube_columns,
            nct_columns=nct_columns,
        )
    except Exception as e:
        return {
            "status": "error",
            "stage": "analytics",
            "language": language,
            "message": str(e),
        }

    # --------------------------------------------------------
    # CHARTS
    # --------------------------------------------------------
    try:
        chart_files = create_all_charts(
            df=df,
            youtube_columns=youtube_columns,
            nct_columns=nct_columns,
            output_root=output_root,
            language=language,
        )
    except Exception as e:
        return {
            "status": "error",
            "stage": "charts",
            "language": language,
            "message": str(e),
        }

    return {
        "status": "success",
        "filename": file.filename,
        "language": language,
        "output_folder": str(output_root),
        "youtube_channels": youtube_columns,
        "nct_columns": nct_columns,
        "results": results,
        "interactive_charts": chart_files,
    }
