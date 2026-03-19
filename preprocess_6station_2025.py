from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "Data" / "sort_data" / "2025_data_6station.parquet"
OUTPUT_DIR = ROOT / "Data" / "sort_data" / "preprocessed_6station"

STATION_IDS = [
    "ST-481",
    "ST-2425",
    "ST-1331",
    "ST-454",
    "ST-453",
    "ST-1482",
]

KOREA_2025_HOLIDAYS = {
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


def explode_by_station(raw_df: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for station_id in STATION_IDS:
        mask = (raw_df["시작_대여소_ID"] == station_id) | (raw_df["종료_대여소_ID"] == station_id)
        station_df = raw_df.loc[mask].copy()
        if station_df.empty:
            continue
        station_df["station_id"] = station_id
        station_df["station_role"] = np.select(
            [
                (station_df["시작_대여소_ID"] == station_id) & (station_df["종료_대여소_ID"] == station_id),
                station_df["시작_대여소_ID"] == station_id,
                station_df["종료_대여소_ID"] == station_id,
            ],
            ["both", "start", "end"],
            default="other",
        )
        parts.append(station_df)

    if not parts:
        return raw_df.head(0).copy()
    return pd.concat(parts, ignore_index=True)


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

    holiday_flag = date.dt.strftime("%Y-%m-%d").isin(KOREA_2025_HOLIDAYS)
    df["is_restingday"] = ((weekday >= 5) | holiday_flag).astype(int)
    return pd.concat([df, weekday_dummies], axis=1)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    hour = pd.to_numeric(df["시간대"], errors="coerce").fillna(0).astype(int)

    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    df["is_noon"] = (hour >= 12).astype(int)
    df["is_rushhour"] = hour.isin([7, 8, 9, 17, 18, 19]).astype(int)
    return df


def add_weather_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rain = pd.to_numeric(df["강수량"], errors="coerce").fillna(0)
    snow = pd.to_numeric(df["적설량"], errors="coerce").fillna(0)
    df["snow_flag"] = ((rain > 0) | (snow > 0)).astype(int)
    return df


def build_dataset(input_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(input_path)
    keep_mask = df["시작_대여소_ID"].isin(STATION_IDS) | df["종료_대여소_ID"].isin(STATION_IDS)
    df = df.loc[keep_mask].copy()

    df["기준_날짜"] = pd.to_datetime(df["기준_날짜"])
    df["전체_이용_거리"] = pd.to_numeric(df["전체_이용_거리"], errors="coerce")
    df = df[df["전체_이용_거리"] > 50].copy()

    df = explode_by_station(df)
    df = add_calendar_features(df)
    df = add_time_features(df)
    df = add_weather_features(df)

    df = df.drop(columns=["전체_건수", "불쾌지수", "적설량"], errors="ignore")
    df = df.sort_values(
        ["station_id", "기준_날짜", "시간대", "시작_대여소_ID", "종료_대여소_ID"]
    ).reset_index(drop=True)
    return df


def save_station_splits(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for station_id in STATION_IDS:
        station_df = df[df["station_id"] == station_id].copy()
        station_df.to_csv(output_dir / f"{station_id}_2025.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", type=Path, default=INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    df = build_dataset(args.input_path)
    save_station_splits(df, args.output_dir)
    print(f"rows={len(df)}")
    print(f"output_dir={args.output_dir}")
    print("files=" + ", ".join(f"{station_id}_2025.csv" for station_id in STATION_IDS))


if __name__ == "__main__":
    main()
