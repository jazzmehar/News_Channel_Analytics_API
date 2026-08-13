import pandas as pd

def _safe_mean(series):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return round(float(values.mean()), 2) if not values.empty else None

def _clean_time(value):
    if pd.isna(value):
        return None

    if hasattr(value, "strftime"):
        try:
            return value.strftime("%H:%M")
        except Exception:
            pass

    text = str(value).strip()

    if ":" in text:
        parts = text.split(":")
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except Exception:
            pass

    return text

def calculate_analytics(df, youtube_columns, nct_columns):
    data = df.copy()

    data["Year"] = pd.to_numeric(data["Year"], errors="coerce")
    data["Week"] = pd.to_numeric(data["Week"], errors="coerce")
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")

    data = data.dropna(
        subset=["Year", "Week", "Date"]
    ).copy()

    data["Year"] = data["Year"].astype(int)
    data["Week"] = data["Week"].astype(int)

    data = data.sort_values(
        ["Year", "Week", "Date", "Time_From"],
        kind="stable"
    ).reset_index(drop=True)

    weeks = (
        data[["Year", "Week"]]
        .drop_duplicates()
        .sort_values(["Year", "Week"])
        .reset_index(drop=True)
    )

    if weeks.empty:
        raise ValueError("No valid Year/Week data found.")

    last6 = weeks.tail(6)
    last4 = weeks.tail(4)
    latest = weeks.iloc[-1]

    latest_year = int(latest["Year"])
    latest_week = int(latest["Week"])

    key6 = set(zip(last6["Year"], last6["Week"]))
    key4 = set(zip(last4["Year"], last4["Week"]))

    data["_KEY"] = list(zip(data["Year"], data["Week"]))

    d6 = data[data["_KEY"].isin(key6)].copy()
    d4 = data[data["_KEY"].isin(key4)].copy()
    dl = data[
        (data["Year"] == latest_year)
        & (data["Week"] == latest_week)
    ].copy()

    if "Time_From" in dl.columns:
        dl["_TIME_SLOT"] = dl["Time_From"].apply(_clean_time)

    results = {
        "latest": {
            "year": latest_year,
            "week": latest_week,
        },
        "periods": {
            "last_6_weeks": [
                {
                    "year": int(row["Year"]),
                    "week": int(row["Week"]),
                }
                for _, row in last6.iterrows()
            ],
            "last_4_weeks": [
                {
                    "year": int(row["Year"]),
                    "week": int(row["Week"]),
                }
                for _, row in last4.iterrows()
            ],
            "latest_week": {
                "year": latest_year,
                "week": latest_week,
            },
        },
        "youtube": {},
        "nct": {},
    }

    # ============================================================
    # YOUTUBE ANALYTICS
    # ============================================================

    for column in youtube_columns:
        if column not in data.columns:
            continue

        d6[column] = pd.to_numeric(d6[column], errors="coerce")
        d4[column] = pd.to_numeric(d4[column], errors="coerce")
        dl[column] = pd.to_numeric(dl[column], errors="coerce")

        weekly = (
            d6.groupby(["Year", "Week"], as_index=False)[column]
            .mean()
            .sort_values(["Year", "Week"])
        )

        daily = (
            d4.groupby("Date", as_index=False)[column]
            .mean()
            .sort_values("Date")
        )

        half = (
            dl.dropna(subset=["_TIME_SLOT"])
            .groupby("_TIME_SLOT", as_index=False)[column]
            .mean()
            .sort_values("_TIME_SLOT")
        )

        weekly_records = []
        for _, row in weekly.iterrows():
            weekly_records.append({
                "year": int(row["Year"]),
                "week": int(row["Week"]),
                "average_views": (
                    round(float(row[column]), 2)
                    if pd.notna(row[column])
                    else None
                ),
            })

        daily_records = []
        for _, row in daily.iterrows():
            daily_records.append({
                "date": row["Date"].strftime("%Y-%m-%d"),
                "average_views": (
                    round(float(row[column]), 2)
                    if pd.notna(row[column])
                    else None
                ),
            })

        half_records = []
        for _, row in half.iterrows():
            half_records.append({
                "time": row["_TIME_SLOT"],
                "average_views": (
                    round(float(row[column]), 2)
                    if pd.notna(row[column])
                    else None
                ),
            })

        results["youtube"][column] = {
            "last_6_weeks": {
                "weekly_average": weekly_records,
                "overall_average": _safe_mean(d6[column]),
            },
            "last_4_weeks": {
                "daily_average": daily_records,
                "overall_average": _safe_mean(d4[column]),
            },
            "latest_week": {
                "half_hourly_average": half_records,
                "overall_average": _safe_mean(dl[column]),
            },
        }

    # ============================================================
    # NCT / CONTENT DETAILS
    # ============================================================

    for column in nct_columns:
        if column not in data.columns:
            continue

        weekly = (
            d6.groupby(["Year", "Week"], as_index=False)[column]
            .agg(
                lambda s:
                s.dropna().iloc[0]
                if not s.dropna().empty
                else None
            )
        )

        daily = (
            d4.groupby("Date", as_index=False)[column]
            .agg(
                lambda s:
                s.dropna().iloc[0]
                if not s.dropna().empty
                else None
            )
        )

        weekly_values = []
        for _, row in weekly.iterrows():
            weekly_values.append({
                "year": int(row["Year"]),
                "week": int(row["Week"]),
                "value": (
                    str(row[column])
                    if pd.notna(row[column])
                    else None
                ),
            })

        daily_values = []
        for _, row in daily.iterrows():
            daily_values.append({
                "date": row["Date"].strftime("%Y-%m-%d"),
                "value": (
                    str(row[column])
                    if pd.notna(row[column])
                    else None
                ),
            })

        latest_values = []
        for _, row in dl.iterrows():
            value = row.get(column)
            if pd.isna(value):
                continue

            latest_values.append({
                "date": row["Date"].strftime("%Y-%m-%d"),
                "time": row.get("_TIME_SLOT"),
                "value": str(value),
            })

        results["nct"][column] = {
            "last_6_weeks": {
                "weekly_values": weekly_values
            },
            "last_4_weeks": {
                "daily_values": daily_values
            },
            "latest_week": {
                "values": latest_values
            },
        }

    results["summary"] = {
        "rows_used": len(data),
        "youtube_channels": len(results["youtube"]),
        "nct_metrics": len(results["nct"]),
        "weekly_period": [
            f"W{int(row['Week'])}"
            for _, row in last6.iterrows()
        ],
        "daily_period": [
            f"W{int(row['Week'])}"
            for _, row in last4.iterrows()
        ],
        "latest_week": f"W{latest_week}",
    }

    return results
