from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
STATION_PATH = ROOT / "Data" / "sort_data" / "preprocessed_6station" / "ST-1331.csv"
RAW_PATH = ROOT / "Data" / "sort_data" / "2024_data_6station.parquet"
OUTPUT_PATH = ROOT / "Data" / "Restitutor" / "resti_dataset.csv"

TRIP_LEVEL_COLUMNS = {
    "집계_기준",
    "시작_대여소_ID",
    "종료_대여소_ID",
    "전체_이용_분",
    "전체_이용_거리",
    "station_role",
}


def load_hourly_station_features() -> pd.DataFrame:
    station_df = pd.read_csv(STATION_PATH, parse_dates=["기준_날짜", "timestamp"])
    feature_columns = [col for col in station_df.columns if col not in TRIP_LEVEL_COLUMNS]
    hourly_features = (
        station_df.loc[:, feature_columns]
        .sort_values(["station_id", "timestamp"])
        .drop_duplicates(subset=["station_id", "timestamp"], keep="first")
        .reset_index(drop=True)
    )
    return hourly_features


def load_usage(station_ids: list[str]) -> pd.DataFrame:
    raw_df = pd.read_parquet(
        RAW_PATH,
        columns=["기준_날짜", "시간대", "시작_대여소_ID", "전체_건수"],
    )
    raw_df["기준_날짜"] = pd.to_datetime(raw_df["기준_날짜"])
    raw_df["timestamp"] = raw_df["기준_날짜"] + pd.to_timedelta(raw_df["시간대"].astype(int), unit="h")

    usage_df = (
        raw_df[raw_df["시작_대여소_ID"].isin(station_ids)]
        .groupby(["시작_대여소_ID", "timestamp"], as_index=False)["전체_건수"]
        .sum()
        .rename(columns={"시작_대여소_ID": "station_id", "전체_건수": "usage"})
    )
    usage_df["usage"] = usage_df["usage"].round().astype(int)
    return usage_df


def build_dataset() -> pd.DataFrame:
    hourly_features = load_hourly_station_features()
    usage_df = load_usage(hourly_features["station_id"].dropna().unique().tolist())

    dataset = (
        hourly_features.merge(usage_df, on=["station_id", "timestamp"], how="left")
        .sort_values(["station_id", "timestamp"])
        .reset_index(drop=True)
    )
    dataset["usage"] = dataset["usage"].fillna(0).astype(int)
    dataset["delta_usage"] = dataset.groupby("station_id")["usage"].diff().fillna(0).astype(int)
    return dataset


def main() -> None:
    dataset = build_dataset()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"saved_rows={len(dataset)}")
    print(f"saved_path={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
