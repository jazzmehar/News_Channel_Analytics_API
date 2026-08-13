from pathlib import Path
import re
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot


HINDI_COLORS = {
    "Aaj Tak": "#FF0000",
    "India TV": "#808080",
    "Republic Bharat": "#006400",
    "TV 9 Bharatvarsh": "#800080",
    "Times Now Navbharat": "#FF69B4",
    "NDTV India": "#FFA500",
    "News 18 India": "#000000",
}

ENGLISH_COLORS = {
    # Exact colours requested for English channels
    "India Today": "#FF0000",       # Red
    "Republic 24x7": "#006400",     # Dark Green
    "CNN News18": "#000000",        # Black
    "WION": "#1F77B4",               # Blue
    "Mirror Now": "#E377C2",         # Pink
    "NDTV 24x7": "#FF8C00",          # Orange
}

CHANNEL_ALIASES = {
    "aajtak": ["aajtak", "aajtakyt"],
    "indiatv": ["indiatv", "indiatvyt"],
    "republicbharat": ["republicbharat", "republicbharatyt"],
    "zee": ["zee", "zeenews", "zeenewsym"],
    "tv9bharatvarsh": ["tv9bharatvarsh", "tv9"],
    "timesnownavbharat": ["timesnownavbharat", "timesnow"],
    "news18india": ["news18india", "news18"],
    "abpnews": ["abpnews", "abp"],
    "goodnewstoday": ["goodnewstoday", "goodnews"],
    "ndtvindia": ["ndtvindia", "ndtv"],
    "news24": ["news24"],
    "cnnnews18": ["cnnnews18", "cnnnews"],
    "indiatoday": ["indiatoday"],
    "republic24x7": ["republic24x7", "republic"],
    "wion": ["wion"],
    "mirrornow": ["mirrornow"],
}


def _safe_name(text):
    text = str(text)
    for char in '<>:"/\\|?*':
        text = text.replace(char, "_")
    return text.strip()


def _clean_name(text):
    text = str(text)
    text = text.replace("AVERAGE of ", "")
    return re.sub(r"\s+", " ", text).strip()


def _normalise(text):
    text = _clean_name(text).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _channel_color(channel, language, index):
    channel_norm = _normalise(channel)

    if str(language).lower() == "hindi":
        for name, color in HINDI_COLORS.items():
            a = _normalise(name)
            if a in channel_norm or channel_norm in a:
                return color
        return "#1F77B4"

    # English: use fixed colours by channel name, not by column order.
    # This prevents colours changing when Excel column order changes.
    for name, color in ENGLISH_COLORS.items():
        a = _normalise(name)
        if a in channel_norm or channel_norm in a:
            return color

    # Fallback for any additional English channel.
    fallback = ["#17BECF", "#9467BD", "#2CA02C", "#8C564B", "#7F7F7F"]
    return fallback[index % len(fallback)]


def _ensure_folder(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _prepare_data(df):
    data = df.copy()

    required = ["Year", "Week", "Date"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data["Year"] = pd.to_numeric(data["Year"], errors="coerce")
    data["Week"] = pd.to_numeric(data["Week"], errors="coerce")
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=required).copy()

    data["Year"] = data["Year"].astype(int)
    data["Week"] = data["Week"].astype(int)

    return data.sort_values(["Year", "Week", "Date"]).reset_index(drop=True)


def _available_weeks(data):
    return (
        data[["Year", "Week"]]
        .drop_duplicates()
        .sort_values(["Year", "Week"])
        .reset_index(drop=True)
    )


def _numeric_valid(data, column):
    if column not in data.columns:
        return False
    return pd.to_numeric(data[column], errors="coerce").notna().sum() > 0


def _match_nct_columns(channel, nct_columns):
    """
    Find NCT/content columns belonging to the selected channel.

    NCT columns may contain:
    FPC, Anchor, Program, Substories, etc.
    They do NOT necessarily contain the word 'NCT'.
    """

    channel_norm = _normalise(channel)

    matches = []

    # Channel aliases
    aliases = {
        "aajtak": [
            "aajtak",
            "aajtakyt"
        ],

        "indiatv": [
            "indiatv",
            "indiatvyt"
        ],

        "republicbharat": [
            "republicbharat",
            "republicbharatyt"
        ],

        "tv9bharatvarsh": [
            "tv9bharatvarsh",
            "tv9"
        ],

        "timesnownavbharat": [
            "timesnownavbharat",
            "timesnow"
        ],

        "ndtvindia": [
            "ndtvindia",
            "ndtv"
        ],

        "news18india": [
            "news18india",
            "news18"
        ],

        "indiatoday": [
            "indiatoday"
        ],

        "cnnnews18": [
            "cnnnews18",
            "cnnnews"
        ],

        "republic24x7": [
            "republic24x7",
            "republic"
        ],

        "wion": [
            "wion"
        ],

        "mirrornow": [
            "mirrornow"
        ]
    }

    possible_names = [channel_norm]

    for key, values in aliases.items():

        if (
            key in channel_norm
            or channel_norm in key
        ):
            possible_names.extend(values)

    # --------------------------------------------------------
    # MATCH CHANNEL-SPECIFIC NCT COLUMNS
    # --------------------------------------------------------

    for col in nct_columns:

        col_norm = _normalise(col)

        for name in possible_names:

            if not name:
                continue

            if (
                name in col_norm
                or col_norm in name
            ):

                if col not in matches:
                    matches.append(col)

                break

    return matches

def _get_all_nct_columns(data, nct_columns):
    result = []
    for col in list(nct_columns or []) + list(data.columns):
        if col in data.columns and "nct" in _normalise(col) and col not in result:
            result.append(col)
    return result


def _metadata_columns(data, youtube_columns, nct_columns):
    known = {
        "Year", "Week", "Date", "Time_From", "Time_To",
        "_DATETIME", "_KEY"
    }
    known.update(youtube_columns or [])
    known.update(nct_columns or [])

    candidates = []
    for col in data.columns:
        if col in known:
            continue
        if pd.api.types.is_numeric_dtype(data[col]):
            continue
        if data[col].notna().sum() > 0:
            candidates.append(col)
    return candidates


def _wrap_text(value, width=55):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    import html
    text = html.escape(str(value).strip())
    if not text:
        return ""

    words = text.split()
    lines, current = [], ""
    for word in words:
        if current and len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = word if not current else current + " " + word
    if current:
        lines.append(current)
    return "<br>".join(lines)


def _format_detail_label(column_name):
    import html
    label = _clean_name(column_name)
    label = re.sub(
        r"^(Aaj Tak|India TV|Republic Bharat|TV 9 Bharatvarsh|"
        r"Times Now Navbharat|NDTV India|News 18 India|Zee News|"
        r"ABP News|Good News Today|News24|CNN News18|India Today|"
        r"Republic 24x7|Mirror Now)\s*[-_:]?\s*",
        "",
        label,
        flags=re.IGNORECASE,
    )
    label = re.sub(r"^NCT\s*[-_:]?\s*", "", label, flags=re.IGNORECASE).strip(" -_:")
    replacements = {
        "fpc": "FPC", "anchor": "Anchor", "program": "Program",
        "programme": "Program", "substories": "Substories",
        "substory": "Substory", "show": "Show", "host": "Host",
        "topic": "Topic", "story": "Story", "details": "Details", "day": "Day",
    }
    label = replacements.get(label.lower(), label)
    return html.escape(label)


def _tooltip_for_row(
    row,
    channel,
    youtube_column,
    nct_columns,
    metadata_columns,
):
    """
    Build ONE complete hover box from ONE exact dataframe row.

    The same row supplies:
    Channel, Date, Time, YouTube Views, NCT, FPC, Anchor,
    Program and Substories.
    """

    import html

    lines = []

    def safe_value(value):
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        return str(value).strip()

    def add_field(label, value, wrap=False):
        value_text = safe_value(value)
        if not value_text:
            return
        if wrap:
            value_text = _wrap_text(value_text, width=65)
        else:
            value_text = html.escape(value_text)
        lines.append(
            f"<b>{html.escape(label)}:</b> {value_text}"
        )

    # ============================================================
    # CHANNEL
    # ============================================================
    lines.append(
        f"<b style='font-size:15px'>{html.escape(_clean_name(channel))}</b>"
    )
    lines.append(
        "<span style='color:#999'>━━━━━━━━━━━━━━━━━━━━━━━━</span>"
    )

    # ============================================================
    # DATE
    # ============================================================
    if "Date" in row.index and pd.notna(row["Date"]):
        try:
            date_text = pd.to_datetime(
                row["Date"]
            ).strftime("%d %b %Y")
        except Exception:
            date_text = safe_value(row["Date"])

        add_field("Date", date_text)

    # ============================================================
    # HALF-HOUR
    # ============================================================
    time_from = safe_value(row.get("Time_From"))
    time_to = safe_value(row.get("Time_To"))

    if time_from or time_to:
        if time_from and time_to:
            add_field("Time", f"{time_from} - {time_to}")
        else:
            add_field("Time", time_from or time_to)

    # ============================================================
    # YOUTUBE VIEWS
    # ============================================================
    if youtube_column in row.index:
        views = pd.to_numeric(
            row[youtube_column],
            errors="coerce",
        )

        if pd.notna(views):
            lines.append(
                f"<b>YouTube Views:</b> {views:,.0f}"
            )

    # ============================================================
    # NCT / CONTENT DETAILS
    # ============================================================
    channel_norm = _normalise(channel)

    # Start with helper's channel matching.
    selected_nct = list(
        _match_nct_columns(
            channel,
            nct_columns or [],
        )
    )

    # Add generic NCT/content columns and channel-specific content
    # columns. This is deliberately broad so FPC / Anchor / Program /
    # Substories are not lost just because the column name differs.
    content_words = (
        "nct",
        "fpc",
        "anchor",
        "program",
        "programme",
        "substories",
        "substory",
        "show",
        "host",
        "topic",
        "story",
    )

    channel_aliases = [
        channel_norm
    ]

    for key, values in CHANNEL_ALIASES.items():
        if key in channel_norm or channel_norm in key:
            channel_aliases.extend(
                _normalise(v) for v in values
            )

    for col in row.index:
        col_norm = _normalise(col)

        if not col_norm:
            continue

        is_content = any(
            word in col_norm
            for word in content_words
        )

        is_channel_specific = any(
            alias and alias in col_norm
            for alias in channel_aliases
        )

        if is_content and (
            is_channel_specific
            or col_norm.startswith("nct")
            or col_norm in {
                "fpc",
                "anchor",
                "program",
                "programme",
                "substories",
                "substory",
            }
        ):
            if col not in selected_nct:
                selected_nct.append(col)

    # Put important fields first.
    priority = (
        "fpc",
        "anchor",
        "program",
        "programme",
        "substories",
        "substory",
    )

    def priority_key(col):
        norm = _normalise(col)
        for i, word in enumerate(priority):
            if word in norm:
                return i
        return len(priority)

    selected_nct = sorted(
        selected_nct,
        key=priority_key,
    )

    added_nct = False

    for col in selected_nct:
        if col not in row.index:
            continue

        value = row[col]
        text = safe_value(value)

        if not text:
            continue

        if not added_nct:
            lines.append(
                "<br><b>━━ NCT / CONTENT DETAILS ━━</b>"
            )
            added_nct = True

        label = _format_detail_label(col)

        # Long Substories/news text gets line wrapping.
        is_long_text = any(
            word in _normalise(col)
            for word in (
                "substories",
                "substory",
                "story",
                "topic",
                "details",
            )
        )

        if is_long_text:
            text_html = _wrap_text(text, width=65)
        else:
            text_html = html.escape(text)

        lines.append(
            f"<b>{label}:</b> {text_html}"
        )

    # ============================================================
    # IMPORTANT: Do NOT add unrelated metadata here.
    # The hover box should contain only:
    # Channel, Date, Time, YouTube Views and NCT/content details.
    # ============================================================

    return "<br>".join(lines)

def _write_html(fig, path, title=None):

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    plot(
        fig,

        filename=str(path),

        auto_open=False,

        include_plotlyjs=True,

        config={
            "scrollZoom": True,
            "displaylogo": False,
            "responsive": True
        }
    )

    return str(path)


def create_weekly_chart(df, youtube_columns, nct_columns, output_folder, language="english"):
    data = _prepare_data(df)
    weeks = _available_weeks(data).tail(6)
    if weeks.empty:
        return None

    keys = set(zip(weeks["Year"], weeks["Week"]))
    data["_KEY"] = list(zip(data["Year"], data["Week"]))
    data = data[data["_KEY"].isin(keys)].copy()

    fig = go.Figure()
    valid_index = 0

    for column in youtube_columns:
        if not _numeric_valid(data, column):
            continue
        data[column] = pd.to_numeric(data[column], errors="coerce")
        weekly = (
            data.groupby(["Year", "Week"], as_index=False)[column]
            .mean()
            .sort_values(["Year", "Week"])
        )
        if weekly.empty:
            continue

        labels = [f"W{int(w)} ({int(y)})" for y, w in zip(weekly["Year"], weekly["Week"])]
        channel = _clean_name(column)
        color = _channel_color(channel, language, valid_index)

        fig.add_trace(go.Scatter(
            x=labels, y=weekly[column], mode="lines+markers", name=channel,
            line={"color": color, "width": 3},
            marker={"size": 8, "color": color},
            hovertemplate=f"<b>{channel}</b><br>Week: %{{x}}<br>Average Views: %{{y:,.2f}}<extra></extra>",
        ))
        valid_index += 1

    fig.update_layout(
        title=f"{str(language).title()} TV Channels — Weekly Average Views — Last 6 Weeks",
        xaxis_title="Week", yaxis_title="Average Views", hovermode="x unified",
        template="plotly_white", height=650, legend_title="Channels",
        margin={"l": 70, "r": 40, "t": 90, "b": 80},
    )

    return _write_html(
        fig,
        _ensure_folder(output_folder) / "ALL_CHANNELS_WEEKLY_LAST_6_WEEKS.html",
    )


def create_daily_chart(df, youtube_columns, nct_columns, output_folder, language="english"):
    data = _prepare_data(df)
    weeks = _available_weeks(data).tail(4)
    if weeks.empty:
        return None

    keys = set(zip(weeks["Year"], weeks["Week"]))
    data["_KEY"] = list(zip(data["Year"], data["Week"]))
    data = data[data["_KEY"].isin(keys)].copy()

    fig = go.Figure()
    valid_index = 0

    for column in youtube_columns:
        if not _numeric_valid(data, column):
            continue
        data[column] = pd.to_numeric(data[column], errors="coerce")
        daily = data.groupby("Date", as_index=False)[column].mean().sort_values("Date")
        if daily.empty:
            continue

        channel = _clean_name(column)
        color = _channel_color(channel, language, valid_index)

        fig.add_trace(go.Scatter(
            x=daily["Date"], y=daily[column], mode="lines+markers", name=channel,
            line={"color": color, "width": 2.5},
            marker={"size": 6, "color": color},
            hovertemplate=(
                f"<b>{channel}</b><br>Date: %{{x|%d %b %Y}}"
                "<br>Daily Average Views: %{y:,.2f}<extra></extra>"
            ),
        ))
        valid_index += 1

    fig.update_layout(
        title=f"{str(language).title()} TV Channels — Daily Average Views — Last 4 Weeks",
        xaxis_title="Date", yaxis_title="Average Views", hovermode="x unified",
        template="plotly_white", height=650, legend_title="Channels",
        margin={"l": 70, "r": 40, "t": 90, "b": 80},
    )
    fig.update_xaxes(rangeslider_visible=True)

    return _write_html(
        fig,
        _ensure_folder(output_folder) / "ALL_CHANNELS_DAILY_LAST_4_WEEKS.html",
    )


def create_half_hourly_chart(
    df,
    youtube_columns,
    nct_columns,
    output_folder,
    language="english",
):
    """
    Create one interactive half-hourly chart for the latest week.

    IMPORTANT:
    Every YouTube point gets its own hover box.
    The hover box is built from the EXACT SAME dataframe row as
    that point, so Date / Time / Views / NCT / Substories etc.
    cannot get mixed between half-hours.
    """

    data = _prepare_data(df)

    weeks = _available_weeks(data)
    if weeks.empty:
        return None

    latest = weeks.iloc[-1]
    latest_year = int(latest["Year"])
    latest_week = int(latest["Week"])

    data = data[
        (data["Year"] == latest_year)
        & (data["Week"] == latest_week)
    ].copy()

    if data.empty:
        return None

    if "Time_From" not in data.columns:
        raise ValueError(
            "Time_From column is required for the half-hourly chart."
        )

    # ------------------------------------------------------------
    # EXACT DATE + TIME FOR EACH HALF-HOUR
    # ------------------------------------------------------------
    date_text = data["Date"].dt.strftime("%Y-%m-%d")
    time_text = data["Time_From"].astype(str).str.strip()

    data["_DATETIME"] = pd.to_datetime(
        date_text + " " + time_text,
        errors="coerce",
    )

    # Fallback for Excel time values that were read differently.
    bad = data["_DATETIME"].isna()

    if bad.any():
        try:
            parsed_time = pd.to_datetime(
                data.loc[bad, "Time_From"],
                errors="coerce",
            )

            data.loc[bad, "_DATETIME"] = (
                data.loc[bad, "Date"].dt.normalize()
                + (
                    parsed_time
                    - parsed_time.dt.normalize()
                )
            )
        except Exception:
            pass

    data = (
        data.dropna(subset=["_DATETIME"])
        .sort_values("_DATETIME")
        .copy()
    )

    if data.empty:
        raise ValueError(
            "No valid Date + Time_From values found for the latest week."
        )

    # ------------------------------------------------------------
    # METADATA
    # ------------------------------------------------------------
    # Keep all supplied NCT columns, plus any textual columns that
    # may contain FPC / Anchor / Program / Substories.
    all_nct_columns = list(dict.fromkeys(
        list(nct_columns or [])
        + [
            col for col in data.columns
            if any(
                key in _normalise(col)
                for key in (
                    "nct",
                    "fpc",
                    "anchor",
                    "program",
                    "programme",
                    "substories",
                    "substory",
                )
            )
        ]
    ))

    metadata_columns = _metadata_columns(
        data,
        youtube_columns,
        all_nct_columns,
    )

    fig = go.Figure()
    color_index = 0

    # ------------------------------------------------------------
    # ONE TRACE PER YOUTUBE CHANNEL
    # ------------------------------------------------------------
    for youtube_column in youtube_columns:

        if not _numeric_valid(data, youtube_column):
            continue

        data[youtube_column] = pd.to_numeric(
            data[youtube_column],
            errors="coerce",
        )

        chart_data = data[
            data[youtube_column].notna()
        ].copy()

        if chart_data.empty:
            continue

        channel = _clean_name(youtube_column)

        color = _channel_color(
            channel,
            language,
            color_index,
        )

        # --------------------------------------------------------
        # ONE HOVER STRING FOR EVERY SINGLE HALF-HOUR POINT
        # --------------------------------------------------------
        hover_text = []

        for _, row in chart_data.iterrows():
            hover_text.append(
                _tooltip_for_row(
                    row=row,
                    channel=channel,
                    youtube_column=youtube_column,
                    nct_columns=all_nct_columns,
                    metadata_columns=metadata_columns,
                )
            )

        # --------------------------------------------------------
        # ADD TRACE
        # --------------------------------------------------------
        fig.add_trace(
            go.Scatter(
                x=chart_data["_DATETIME"],
                y=chart_data[youtube_column],

                mode="lines+markers",
                name=channel,

                line={
                    "color": color,
                    "width": 2.5,
                },

                marker={
                    "color": color,
                    "size": 8,
                    "line": {
                        "color": color,
                        "width": 1,
                    },
                },

                # IMPORTANT:
                # One hover string for every point.
                customdata=hover_text,

                hovertemplate=(
                    "%{customdata}"
                    "<extra></extra>"
                ),

                hoverlabel={
                    "bgcolor": "white",
                    "bordercolor": color,
                    "font": {
                        "color": "black",
                        "size": 12,
                        "family": "Arial",
                    },
                    "align": "left",
                    "namelength": -1,
                },
            )
        )

        color_index += 1

    if not fig.data:
        raise ValueError(
            "No valid YouTube channel columns were found "
            "for the half-hourly chart."
        )

    # ------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------
    fig.update_layout(
        title=(
            f"{str(language).title()} TV Channels — "
            f"Half-Hourly Performance — "
            f"Latest Week W{latest_week}, {latest_year}"
        ),
        xaxis_title="Date + Time",
        yaxis_title="Views",

        # Hover the nearest individual half-hour point.
        hovermode="closest",

        template="plotly_white",
        height=850,
        legend_title="Channels",

        margin={
            "l": 80,
            "r": 40,
            "t": 110,
            "b": 100,
        },
    )

    # ------------------------------------------------------------
    # RANGE SLIDER + QUICK ZOOM
    # ------------------------------------------------------------
    fig.update_xaxes(
        rangeslider_visible=True,
        rangeselector={
            "buttons": [
                {
                    "count": 6,
                    "label": "6 Hours",
                    "step": "hour",
                    "stepmode": "backward",
                },
                {
                    "count": 12,
                    "label": "12 Hours",
                    "step": "hour",
                    "stepmode": "backward",
                },
                {
                    "count": 1,
                    "label": "1 Day",
                    "step": "day",
                    "stepmode": "backward",
                },
                {
                    "step": "all",
                    "label": "Full Week",
                },
            ]
        },
    )

    # ------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------
    output_folder = _ensure_folder(output_folder)

    path = (
        output_folder
        / f"ALL_CHANNELS_HALF_HOURLY_"
          f"W{latest_week}_{latest_year}.html"
    )

    return _write_html(
        fig,
        path,
        "Half-Hourly TV Analytics",
    )


def create_all_charts(
    df,
    youtube_columns,
    nct_columns,
    output_root,
    language="english",
):
    output_root = Path(output_root)

    weekly_folder = output_root / "weekly"
    daily_folder = output_root / "daily"
    half_hourly_folder = output_root / "half_hourly"

    weekly_file = create_weekly_chart(
        df, youtube_columns, nct_columns, weekly_folder, language
    )
    daily_file = create_daily_chart(
        df, youtube_columns, nct_columns, daily_folder, language
    )
    half_hourly_file = create_half_hourly_chart(
        df, youtube_columns, nct_columns, half_hourly_folder, language
    )

    return {
        "weekly": [weekly_file] if weekly_file else [],
        "daily": [daily_file] if daily_file else [],
        "half_hourly": [half_hourly_file] if half_hourly_file else [],
    }
