from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
STATION_ID = "ST-3279"
INPUT_OUTPUT_PATHS = (
    (
        ROOT / "Data" / "sort_data" / "2024_data_ST-3279.parquet",
        ROOT / "Data" / "sort_data" / "preprocessed_6station" / "ST-3279.csv",
    ),
    (
        ROOT / "Data" / "sort_data" / "2025_data_ST-3279.parquet",
        ROOT / "Data" / "sort_data" / "preprocessed_6station" / "ST-3279_2025.csv",
    ),
)
KOREA_HOLIDAYS = {
    "2024-01-01",
    "2024-02-09",
    "2024-02-10",
    "2024-02-11",
    "2024-02-12",
    "2024-03-01",
    "2024-04-10",
    "2024-05-05",
    "2024-05-06",
    "2024-05-15",
    "2024-06-06",
    "2024-08-15",
    "2024-09-16",
    "2024-09-17",
    "2024-09-18",
    "2024-10-03",
    "2024-10-09",
    "2024-12-25",
    "2025-01-01",
    "2025-01-27",
    "2025-01-28",
    "2025-01-29",
    "2025-01-30",
    "2025-03-01",
    "2025-03-03",
    "2025-05-05",
    "2025-05-06",
    "2025-06-03",
    "2025-06-06",
    "2025-08-15",
    "2025-10-03",
    "2025-10-05",
    "2025-10-06",
    "2025-10-07",
    "2025-10-08",
    "2025-10-09",
    "2025-12-25",
}


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    date = pd.to_datetime(df["기준_날짜"])
    month = date.dt.month
    weekday = date.dt.dayofweek

    df["year"] = date.dt.year
    df["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12.0)

    weekday_dummies = pd.get_dummies(weekday, prefix="weekday", dtype=int)
    weekday_dummies = weekday_dummies.reindex(columns=[f"weekday_{i}" for i in range(7)], fill_value=0)

    holiday_flag = date.dt.strftime("%Y-%m-%d").isin(KOREA_HOLIDAYS)
    df["is_restingday"] = ((weekday >= 5) | holiday_flag).astype(int)
    return pd.concat([df, weekday_dummies], axis=1)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    hour = pd.to_numeric(df["시간대"], errors="coerce").fillna(0).astype(int)

    df["시간대"] = hour
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    df["is_noon"] = (hour >= 12).astype(int)
    df["is_rushhour"] = hour.isin([7, 8, 9, 17, 18, 19]).astype(int)
    return df


def add_weather_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rain = pd.to_numeric(df["강수량"], errors="coerce").fillna(0.0)
    snow = pd.to_numeric(df["적설량"], errors="coerce").fillna(0.0)

    df["강수량"] = rain
    df["snow_flag"] = ((rain > 0) | (snow > 0)).astype(int)
    return df


def add_station_columns(df: pd.DataFrame) -> pd.DataFrame:
    start_mask = df["시작_대여소_ID"] == STATION_ID
    end_mask = df["종료_대여소_ID"] == STATION_ID

    df = df.loc[start_mask | end_mask].copy()
    start_mask = df["시작_대여소_ID"] == STATION_ID
    end_mask = df["종료_대여소_ID"] == STATION_ID

    df["station_id"] = STATION_ID
    df["station_role"] = np.select(
        [start_mask & end_mask, start_mask, end_mask],
        ["both", "start", "end"],
        default="other",
    )
    return df


def preprocess(input_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(input_path)
    df["기준_날짜"] = pd.to_datetime(df["기준_날짜"])
    df["전체_이용_거리"] = pd.to_numeric(df["전체_이용_거리"], errors="coerce")
    df = df[df["전체_이용_거리"] > 50].copy()

    df = add_station_columns(df)
    df = add_calendar_features(df)
    df = add_time_features(df)
    df = add_weather_features(df)

    df = df.drop(columns=["전체_건수", "불쾌지수", "적설량"], errors="ignore")
    df = df.sort_values(["기준_날짜", "시간대", "시작_대여소_ID", "종료_대여소_ID"]).reset_index(drop=True)
    return df


def main() -> None:
    for input_path, output_path in INPUT_OUTPUT_PATHS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        preprocess(input_path).to_csv(output_path, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
