from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "Data" / "2024_ST-1023.csv"
META_PATH = ROOT / "Data" / "은평구_스테이션_군집화_1차_자전거댓수_추가.csv"
OUTPUT_PATH = ROOT / "Data" / "2024_ST-1023_model_features.csv"


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


FEATURE_COLUMNS = [
    "hour",
    "weekday",
    "is_weekend",
    "온도",
    "습도",
    "불쾌지수",
    "강수량",
    "적설량",
    "위도",
    "경도",
    "cluster_12_custom",
    "LCD",
    "QR",
    "lag_1h",
    "lag_2h",
    "lag_24h",
    "rolling_3h",
    "hour_sin",
    "hour_cos",
    "is_holiday",
]


def build_dataset() -> pd.DataFrame:
    raw = pd.read_csv(RAW_PATH)
    raw["datetime"] = pd.to_datetime(raw["기준_날짜"].astype(str)) + pd.to_timedelta(raw["시간대"], unit="h")

    hourly = (
        raw.groupby(["datetime", "시작_대여소_ID"], as_index=False)
        .agg(
            {
                "전체_건수": "sum",
                "온도": "first",
                "습도": "first",
                "불쾌지수": "first",
                "강수량": "first",
                "적설량": "first",
            }
        )
        .sort_values("datetime")
    )

    station_id = hourly["시작_대여소_ID"].iat[0]
    full_time = pd.date_range(
        hourly["datetime"].min().normalize(),
        hourly["datetime"].max().normalize() + pd.Timedelta(hours=23),
        freq="h",
    )
    df = pd.DataFrame({"datetime": full_time})
    df["시작_대여소_ID"] = station_id
    df = df.merge(hourly, on=["datetime", "시작_대여소_ID"], how="left")
    df["전체_건수"] = df["전체_건수"].fillna(0.0)

    weather_cols = ["온도", "습도", "불쾌지수", "강수량", "적설량"]
    df[weather_cols] = (
        df[weather_cols]
        .interpolate(method="linear", limit_direction="both")
        .ffill()
        .bfill()
    )

    meta = pd.read_csv(META_PATH, encoding="utf-8-sig")
    meta = meta.rename(columns={"대여소_ID": "시작_대여소_ID"})
    meta_cols = ["시작_대여소_ID", "위도", "경도", "cluster_12_custom", "LCD", "QR"]
    df = df.merge(meta[meta_cols], on="시작_대여소_ID", how="left")

    df["hour"] = df["datetime"].dt.hour
    df["weekday"] = df["datetime"].dt.dayofweek
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["is_holiday"] = df["datetime"].dt.strftime("%Y-%m-%d").isin(KOREA_2024_HOLIDAYS).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    df["lag_1h"] = df["전체_건수"].shift(1)
    df["lag_2h"] = df["전체_건수"].shift(2)
    df["lag_24h"] = df["전체_건수"].shift(24)
    df["rolling_3h"] = df["전체_건수"].shift(1).rolling(3).mean()

    df = df.dropna().reset_index(drop=True)
    df["target"] = df["전체_건수"]
    df["date"] = df["datetime"].dt.date
    return df


def fit_ridge_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    alpha: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0)
    std[std == 0] = 1.0

    X_train_scaled = (X_train - mean) / std
    X_test_scaled = (X_test - mean) / std

    train_design = np.column_stack([np.ones(len(X_train_scaled)), X_train_scaled])
    test_design = np.column_stack([np.ones(len(X_test_scaled)), X_test_scaled])

    penalty = np.eye(train_design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coef = np.linalg.solve(train_design.T @ train_design + penalty, train_design.T @ y_train)
    pred = test_design @ coef
    return pred, coef, std


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = np.sum((y_true - np.mean(y_true)) ** 2)
    if denom == 0:
        return 0.0
    return float(1 - np.sum((y_true - y_pred) ** 2) / denom)


def main() -> None:
    df = build_dataset()
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    split_idx = int(len(df) * 0.8)
    train = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()

    X_train = train[FEATURE_COLUMNS].to_numpy(dtype=float)
    X_test = test[FEATURE_COLUMNS].to_numpy(dtype=float)
    y_train = np.log1p(train["target"].to_numpy(dtype=float))
    y_test = test["target"].to_numpy(dtype=float)

    pred_log, _, _ = fit_ridge_regression(X_train, y_train, X_test, alpha=5.0)
    pred = np.expm1(pred_log)
    pred = np.clip(pred, 0.0, None)

    station_id = df["시작_대여소_ID"].iat[0]
    print(f"source_file={RAW_PATH.name}")
    print(f"station_id={station_id}")
    print(f"dataset_rows={len(df)}")
    print(f"train_rows={len(train)}")
    print(f"test_rows={len(test)}")
    print(f"test_start={test['datetime'].min()}")
    print(f"test_end={test['datetime'].max()}")
    print(f"MAE={mae(y_test, pred):.4f}")
    print(f"RMSE={rmse(y_test, pred):.4f}")
    print(f"R2={r2(y_test, pred):.4f}")
    print(f"feature_dataset={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
