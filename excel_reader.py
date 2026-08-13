from pathlib import Path
import re
import pandas as pd


# ============================================================
# REQUIRED BASE COLUMNS
# ============================================================

BASE_COLUMNS = [
    "Year",
    "Week",
    "Date",
    "Day",
    "Time_From",
    "Time_To",
]


# ============================================================
# TEXT CLEANING
# ============================================================

def _clean_column_name(value):
    if value is None or pd.isna(value):
        return ""

    text = str(value)

    # Remove line breaks/tabs and collapse spaces
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _normalise_header(text):
    text = _clean_column_name(text).lower()

    # Normalize different dash characters
    text = text.replace("–", "-").replace("—", "-")

    return text


def _make_unique_columns(columns):
    seen = {}
    result = []

    for col in columns:
        col = _clean_column_name(col) or "Unnamed"

        count = seen.get(col, 0)

        if count == 0:
            result.append(col)
        else:
            result.append(f"{col}.{count}")

        seen[col] = count + 1

    return result


# ============================================================
# YOUTUBE COLUMN DETECTION
#
# Supports examples such as:
#   India Today TV - YT
#   AVERAGE of India Today TV - YT
#   India Today Television - YT
#   CNN News18 - YT
#   Aaj Tak - YT
#   ..._YT
# ============================================================

def _is_youtube_column(column):

    text = _normalise_header(column)

    if not text:
        return False

    # Very broad but controlled detection.
    # We specifically look for YouTube marker YT at the end,
    # allowing spaces, punctuation and common Excel prefixes.
    if re.search(r"(?:^|[\s_-])yt\s*$", text):
        return True

    # Some workbooks may contain the word YouTube itself.
    if re.search(r"youtube\s*$", text):
        return True

    return False


# ============================================================
# NCT / CONTENT COLUMN DETECTION
# ============================================================

def _is_content_column(column):

    text = _normalise_header(column)

    if not text:
        return False

    prefixes = (
        "fpc ",
        "anchor ",
        "program ",
        "substories ",
    )

    if text.startswith(prefixes):
        return True

    # Additional common NCT naming patterns
    if "-hsm15+" in text:
        return True

    if "-hsm-u 15+" in text:
        return True

    if "-shr%" in text:
        return True

    return False


# ============================================================
# HEADER SCORING
# ============================================================

def _header_score(values):

    cleaned = [
        _normalise_header(v)
        for v in values
        if _clean_column_name(v)
    ]

    if not cleaned:
        return 0

    score = 0

    # Base columns
    for col in BASE_COLUMNS:
        if _normalise_header(col) in cleaned:
            score += 10

    # YouTube columns
    youtube_count = sum(
        1 for value in cleaned
        if _is_youtube_column(value)
    )

    score += min(youtube_count, 20) * 3

    # NCT/content columns
    content_count = sum(
        1 for value in cleaned
        if _is_content_column(value)
    )

    score += min(content_count, 20) * 2

    return score


# ============================================================
# FIND REAL HEADER ROW
#
# We scan the first 60 rows instead of assuming row 0.
# This is important because the Hindi and English workbooks
# can have different header arrangements.
# ============================================================

def _find_header_row(file_path, sheet_name="Sheet1", scan_rows=60):

    preview = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=None,
        nrows=scan_rows,
    )

    if preview.empty:
        raise ValueError("The Excel sheet appears to be empty.")

    candidates = []

    for row_index in range(len(preview)):

        values = preview.iloc[row_index].tolist()

        score = _header_score(values)

        if score > 0:
            candidates.append(
                (score, row_index)
            )

    if not candidates:
        raise ValueError(
            "Could not find a recognizable Excel header row. "
            "The workbook may use an unexpected layout."
        )

    # Prefer rows containing the required base columns.
    base_candidates = []

    for score, row_index in candidates:

        values = {
            _clean_column_name(v)
            for v in preview.iloc[row_index].tolist()
            if pd.notna(v)
        }

        if set(BASE_COLUMNS).issubset(values):
            base_candidates.append(
                (score, row_index)
            )

    if base_candidates:

        # Highest score, and if tied use the earliest row.
        base_candidates.sort(
            key=lambda x: (-x[0], x[1])
        )

        return base_candidates[0][1]

    # If exact base columns were not found, use best scored row.
    candidates.sort(
        key=lambda x: (-x[0], x[1])
    )

    return candidates[0][1]


# ============================================================
# READ EXCEL
# ============================================================

def read_tv_excel(file_path):

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Excel file not found: {file_path}"
        )

    if file_path.suffix.lower() not in {
        ".xlsx",
        ".xls",
    }:
        raise ValueError(
            "Please provide an Excel file (.xlsx or .xls)."
        )

    # --------------------------------------------------------
    # FIND SHEET
    # --------------------------------------------------------

    try:
        excel_file = pd.ExcelFile(file_path)
    except Exception as e:
        raise ValueError(
            f"Could not open Excel file: {e}"
        )

    # Prefer Sheet1, otherwise first sheet
    if "Sheet1" in excel_file.sheet_names:
        sheet_name = "Sheet1"
    else:
        sheet_name = excel_file.sheet_names[0]

    # --------------------------------------------------------
    # FIND HEADER
    # --------------------------------------------------------

    header_row = _find_header_row(
        file_path,
        sheet_name=sheet_name,
        scan_rows=60,
    )

    # --------------------------------------------------------
    # READ DATA
    # --------------------------------------------------------

    data = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=header_row,
    )

    # Clean column names
    data.columns = _make_unique_columns(
        data.columns
    )

    # Remove completely empty columns
    data = data.dropna(
        axis=1,
        how="all"
    )

    # --------------------------------------------------------
    # BASE COLUMN CHECK
    # --------------------------------------------------------

    missing = [
        col
        for col in BASE_COLUMNS
        if col not in data.columns
    ]

    if missing:

        # Sometimes the header is one row above/below the best
        # detected row. Give a useful error rather than silently
        # producing an empty chart.
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing)
            + f". Detected header row: {header_row + 1}"
        )

    # --------------------------------------------------------
    # CONVERT BASE FIELDS
    # --------------------------------------------------------

    data["Year"] = pd.to_numeric(
        data["Year"],
        errors="coerce"
    )

    data["Week"] = pd.to_numeric(
        data["Week"],
        errors="coerce"
    )

    data["Date"] = pd.to_datetime(
        data["Date"],
        errors="coerce"
    )

    data = data.dropna(
        subset=[
            "Year",
            "Week",
            "Date",
        ]
    ).copy()

    data["Year"] = data["Year"].astype(int)
    data["Week"] = data["Week"].astype(int)

    # --------------------------------------------------------
    # DETECT YOUTUBE COLUMNS
    # --------------------------------------------------------

    youtube_columns = [
        col
        for col in data.columns
        if _is_youtube_column(col)
    ]

    # --------------------------------------------------------
    # DETECT NCT COLUMNS
    # --------------------------------------------------------

    nct_columns = [
        col
        for col in data.columns
        if _is_content_column(col)
    ]

    # --------------------------------------------------------
    # CONVERT YOUTUBE VALUES TO NUMERIC
    # --------------------------------------------------------

    for col in youtube_columns:

        data[col] = pd.to_numeric(
            data[col],
            errors="coerce"
        )

    # --------------------------------------------------------
    # VALIDATE YOUTUBE DATA
    # --------------------------------------------------------

    if not youtube_columns:

        # Give useful diagnostic information.
        possible_columns = [
            str(col)
            for col in data.columns
            if (
                "yt" in _normalise_header(col)
                or "youtube" in _normalise_header(col)
            )
        ]

        diagnostic = ""

        if possible_columns:
            diagnostic = (
                " Possible YouTube-related columns found: "
                + ", ".join(possible_columns[:20])
            )

        raise ValueError(
            "No YouTube columns were detected."
            + diagnostic
            + " Check the Excel header row and column names."
        )

    # --------------------------------------------------------
    # SORT DATA
    # --------------------------------------------------------

    sort_columns = [
        "Year",
        "Week",
        "Date",
    ]

    if "Time_From" in data.columns:
        sort_columns.append("Time_From")

    data = data.sort_values(
        sort_columns,
        kind="stable",
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # LATEST PERIOD
    # --------------------------------------------------------

    if data.empty:
        raise ValueError(
            "No usable data rows were found after cleaning."
        )

    latest = data.iloc[-1]

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "data": data,

        "total_rows": len(data),

        "latest_year": int(
            latest["Year"]
        ),

        "latest_week": int(
            latest["Week"]
        ),

        "base_columns": BASE_COLUMNS.copy(),

        "youtube_columns": youtube_columns,

        "nct_columns": nct_columns,

        "sheet_name": sheet_name,

        "header_row": header_row + 1,
    }
