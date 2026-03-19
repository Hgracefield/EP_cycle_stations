from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "Data" / "sort_data" / "2024_data_6station.parquet"
STATION_META_PATH = ROOT / "Data" / "은평구_스테이션_군집화_1차.csv"
SUBWAY_DAILY_PATH = ROOT / "Data" / "Restitutor" / "subway_24.csv"
SUBWAY_LL_PATH = ROOT / "Data" / "Restitutor" / "subway_24_ll.csv"
REGION_PATH = ROOT / "Data" / "Restitutor" / "dist_latlng.csv"
METEO_CACHE_PATH = ROOT / "Data" / "Restitutor" / "meteo_2023-12-31.csv"
OUTPUT_DIR = ROOT / "Data" / "sort_data" / "preprocessed_6station"

STATION_IDS = [
    "ST-481",
    "ST-2425",
    "ST-1331",
    "ST-454",
    "ST-453",
    "ST-1482",
]

KOREA_2024_HOLIDAYS = {
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
}


def haversine_m(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    radius_m = 6_371_000.0
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2.astype(float))
    lon2 = np.radians(lon2.astype(float))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * radius_m * np.arcsin(np.sqrt(a))


def extract_dong(*values: object) -> str | None:
    pattern = re.compile(r"([가-힣0-9]+동)")
    for value in values:
        text = "" if pd.isna(value) else str(value)
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def load_station_meta() -> pd.DataFrame:
    meta = pd.read_csv(STATION_META_PATH, encoding="utf-8-sig")
    meta = meta.rename(columns={"대여소_ID": "station_id"})
    meta = meta[meta["station_id"].isin(STATION_IDS)].copy()
    meta["station_dong"] = meta.apply(lambda row: extract_dong(row.get("주소1"), row.get("주소2")), axis=1)
    return meta[["station_id", "위도", "경도", "주소1", "주소2", "station_dong"]].drop_duplicates("station_id")


def fetch_boundary_meteo(lat: float, lon: float, timezone: str = "Asia/Seoul") -> pd.DataFrame:
    if METEO_CACHE_PATH.exists():
        cached = pd.read_csv(METEO_CACHE_PATH)
        cached["timestamp"] = pd.to_datetime(cached["timestamp"])
        return cached

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2023-12-31",
        "end_date": "2023-12-31",
        "hourly": "temperature_2m,relative_humidity_2m",
        "timezone": timezone,
    }
    url = f"https://archive-api.open-meteo.com/v1/archive?{urlencode(params)}"
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    hourly = payload["hourly"]
    weather = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(hourly["time"]),
            "온도": hourly["temperature_2m"],
            "습도": hourly["relative_humidity_2m"],
        }
    )
    METEO_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(METEO_CACHE_PATH, index=False, encoding="utf-8-sig")
    return weather


def build_temp_lag_lookup(raw_df: pd.DataFrame, boundary_weather: pd.DataFrame) -> pd.Series:
    hourly_temp = (
        raw_df.groupby("timestamp", as_index=False)["온도"]
        .mean()
        .sort_values("timestamp")
    )
    lookup = pd.concat(
        [boundary_weather[["timestamp", "온도"]], hourly_temp],
        ignore_index=True,
    ).drop_duplicates("timestamp")
    full_index = pd.date_range(lookup["timestamp"].min(), lookup["timestamp"].max(), freq="h")
    lookup = lookup.set_index("timestamp").reindex(full_index)
    lookup["온도"] = lookup["온도"].interpolate(limit_direction="both").ffill().bfill()
    lookup.index.name = "timestamp"
    return lookup["온도"]


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
    return pd.concat(parts, ignore_index=True)


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = df["기준_날짜"].dt.year
    month = df["기준_날짜"].dt.month
    weekday = df["기준_날짜"].dt.dayofweek
    month_angle = 2 * np.pi * (month - 1) / 12.0
    df["month_sin"] = np.sin(month_angle)
    df["month_cos"] = np.cos(month_angle)
    weekday_dummies = pd.get_dummies(weekday, prefix="weekday", dtype=int)
    weekday_dummies = weekday_dummies.reindex(columns=[f"weekday_{i}" for i in range(7)], fill_value=0)
    holiday_flag = df["기준_날짜"].dt.strftime("%Y-%m-%d").isin(KOREA_2024_HOLIDAYS)
    df["is_restingday"] = ((weekday >= 5) | holiday_flag).astype(int)
    return pd.concat([df, weekday_dummies], axis=1)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    hour = df["시간대"].astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    df["is_noon"] = (hour >= 12).astype(int)
    df["is_rushhour"] = hour.isin([7, 8, 9, 17, 18, 19]).astype(int)
    return df


def build_region_features(station_meta: pd.DataFrame) -> pd.DataFrame:
    region = pd.read_csv(REGION_PATH)
    region_month = (
        region.groupby(["dong", "month"], as_index=False)
        .agg(
            {
                "총인구": "sum",
                "평일 외출이 적은 집단": "sum",
                "휴일 외출이 적은 집단": "sum",
                "출근소요시간 및 근무시간이 많은 집단": "sum",
                "외출이 매우 많은 집단": "sum",
                "lat": "first",
                "lng": "first",
            }
        )
        .copy()
    )
    population = region_month["총인구"].replace(0, np.nan)
    region_month["residential_index"] = (
        region_month["평일 외출이 적은 집단"] + region_month["휴일 외출이 적은 집단"]
    ) / (2.0 * population)
    region_month["business_index"] = region_month["출근소요시간 및 근무시간이 많은 집단"] / population
    region_month["tourism_index"] = region_month["외출이 매우 많은 집단"] / population

    rows: list[dict[str, object]] = []
    for station in station_meta.itertuples(index=False):
        for month in range(1, 13):
            month_region = region_month[region_month["month"] == month].copy()
            if month_region.empty:
                continue
            month_region["dist_m"] = haversine_m(
                station.위도,
                station.경도,
                month_region["lat"].to_numpy(),
                month_region["lng"].to_numpy(),
            )
            matched = month_region[month_region["dist_m"] <= 200].copy()
            if matched.empty and station.station_dong:
                matched = month_region[month_region["dong"] == station.station_dong].copy()
            if matched.empty:
                matched = month_region.nsmallest(1, "dist_m").copy()

            rows.append(
                {
                    "station_id": station.station_id,
                    "month": month,
                    "residential_index": matched["residential_index"].mean(),
                    "business_index": matched["business_index"].mean(),
                    "tourism_index": matched["tourism_index"].mean(),
                }
            )

    return pd.DataFrame(rows)


def build_subway_features(station_meta: pd.DataFrame) -> pd.DataFrame:
    subway_daily = pd.read_csv(SUBWAY_DAILY_PATH)
    subway_daily["날짜"] = pd.to_datetime(subway_daily["날짜"])
    subway_ll = pd.read_csv(SUBWAY_LL_PATH)

    station_to_subways: dict[str, list[str]] = {}
    for station in station_meta.itertuples(index=False):
        ll = subway_ll.copy()
        ll["dist_m"] = haversine_m(
            station.위도,
            station.경도,
            ll["위도"].to_numpy(),
            ll["경도"].to_numpy(),
        )
        nearby_names = ll.loc[ll["dist_m"] <= 200, "역명"].drop_duplicates().tolist()
        station_to_subways[station.station_id] = nearby_names

    subway_daily["total_riders"] = subway_daily[["새벽", "출근", "낮", "퇴근"]].sum(axis=1)
    transit_raw = subway_daily.groupby(["날짜", "역명"], as_index=False)["total_riders"].sum()
    max_total = transit_raw["total_riders"].max() or 1.0
    transit_raw["transit_index"] = transit_raw["total_riders"] / max_total

    commute_in_raw = (
        subway_daily[subway_daily["구분"] == "하차"]
        .groupby(["날짜", "역명"], as_index=False)["출근_ratio"]
        .mean()
        .rename(columns={"출근_ratio": "commute_in_index"})
    )
    commute_out_raw = (
        subway_daily[subway_daily["구분"] == "승차"]
        .groupby(["날짜", "역명"], as_index=False)["퇴근_ratio"]
        .mean()
        .rename(columns={"퇴근_ratio": "commute_out_index"})
    )

    date_index = pd.DataFrame({"기준_날짜": sorted(subway_daily["날짜"].drop_duplicates().tolist())})
    rows: list[pd.DataFrame] = []
    for station_id in STATION_IDS:
        nearby_names = station_to_subways.get(station_id, [])
        if not nearby_names:
            empty = date_index.copy()
            empty["station_id"] = station_id
            empty["transit_index"] = 0.0
            empty["commute_in_index"] = 0.0
            empty["commute_out_index"] = 0.0
            rows.append(empty)
            continue

        transit = (
            transit_raw[transit_raw["역명"].isin(nearby_names)]
            .groupby("날짜", as_index=False)["transit_index"]
            .sum()
            .rename(columns={"날짜": "기준_날짜"})
        )
        commute_in = (
            commute_in_raw[commute_in_raw["역명"].isin(nearby_names)]
            .groupby("날짜", as_index=False)["commute_in_index"]
            .mean()
            .rename(columns={"날짜": "기준_날짜"})
        )
        commute_out = (
            commute_out_raw[commute_out_raw["역명"].isin(nearby_names)]
            .groupby("날짜", as_index=False)["commute_out_index"]
            .mean()
            .rename(columns={"날짜": "기준_날짜"})
        )
        merged = (
            date_index.copy()
            .assign(station_id=station_id)
            .merge(transit, on="기준_날짜", how="left")
            .merge(commute_in, on="기준_날짜", how="left")
            .merge(commute_out, on="기준_날짜", how="left")
            .fillna(0.0)
        )
        rows.append(merged)

    return pd.concat(rows, ignore_index=True)


def build_dataset() -> pd.DataFrame:
    raw_df = pd.read_parquet(INPUT_PATH)
    keep_mask = raw_df["시작_대여소_ID"].isin(STATION_IDS) | raw_df["종료_대여소_ID"].isin(STATION_IDS)
    raw_df = raw_df.loc[keep_mask].copy()
    raw_df["기준_날짜"] = pd.to_datetime(raw_df["기준_날짜"])
    raw_df = raw_df[pd.to_numeric(raw_df["전체_이용_거리"], errors="coerce") > 50].copy()
    raw_df["timestamp"] = raw_df["기준_날짜"] + pd.to_timedelta(raw_df["시간대"].astype(int), unit="h")

    station_meta = load_station_meta()
    boundary_weather = fetch_boundary_meteo(
        lat=station_meta["위도"].mean(),
        lon=station_meta["경도"].mean(),
    )
    temp_lookup = build_temp_lag_lookup(raw_df, boundary_weather)

    df = explode_by_station(raw_df)
    df["temp_lag_1hr"] = (df["timestamp"] - pd.Timedelta(hours=1)).map(temp_lookup)
    df = df.merge(station_meta, on="station_id", how="left")
    df = add_calendar_features(df)
    df = add_time_features(df)

    region_features = build_region_features(station_meta)
    subway_features = build_subway_features(station_meta)
    df["month"] = df["기준_날짜"].dt.month
    df = df.merge(region_features, on=["station_id", "month"], how="left")
    df = df.merge(subway_features, on=["station_id", "기준_날짜"], how="left")

    df["snow_flag"] = (pd.to_numeric(df["적설량"], errors="coerce").fillna(0) > 0).astype(int)
    feature_fill_cols = [
        "temp_lag_1hr",
        "residential_index",
        "business_index",
        "tourism_index",
        "transit_index",
        "commute_in_index",
        "commute_out_index",
    ]
    df[feature_fill_cols] = df[feature_fill_cols].fillna(0.0)
    df = df.drop(columns=["전체_건수", "불쾌지수", "적설량", "주소1", "주소2"], errors="ignore")
    df = df.sort_values(["station_id", "timestamp", "시작_대여소_ID", "종료_대여소_ID"]).reset_index(drop=True)
    return df


def save_station_splits(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for station_id in STATION_IDS:
        station_df = df[df["station_id"] == station_id].copy()
        station_df.to_csv(output_dir / f"{station_id}.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    df = build_dataset()
    save_station_splits(df, args.output_dir)
    print(f"rows={len(df)}")
    print(f"output_dir={args.output_dir}")
    print("files=" + ", ".join(f"{station_id}.csv" for station_id in STATION_IDS))


if __name__ == "__main__":
    main()
