from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "Data" / "2024_st_hhj.csv"
DEFAULT_FEATURES = ROOT / "Data" / "2024_st_hhj_hourly_features.csv"
DEFAULT_PREDICTIONS = ROOT / "Data" / "2024_st_hhj_hourly_predictions.csv"

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


def find_station_meta_file() -> Path | None:
    for path in sorted((ROOT / "Data").glob("*군집화*1차.csv")):
        if "추가" not in path.name:
            return path
    return None


def load_station_meta(station_ids: list[str]) -> pd.DataFrame:
    meta_path = find_station_meta_file()
    if meta_path is None:
        return pd.DataFrame({"시작_대여소_ID": station_ids})

    meta = pd.read_csv(meta_path, encoding="utf-8-sig")
    meta = meta.rename(columns={"대여소_ID": "시작_대여소_ID"})

    keep_cols = [
        "시작_대여소_ID",
        "위도",
        "경도",
        "cluster_12_custom",
        "연간_전체건수",
    ]
    keep_cols = [col for col in keep_cols if col in meta.columns]
    meta = meta[keep_cols].drop_duplicates("시작_대여소_ID")

    missing = sorted(set(station_ids) - set(meta["시작_대여소_ID"]))
    if missing:
        filler = pd.DataFrame({"시작_대여소_ID": missing})
        meta = pd.concat([meta, filler], ignore_index=True, sort=False)

    return meta


def build_hourly_dataset(input_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(input_path, encoding="utf-8-sig")
    raw["datetime"] = pd.to_datetime(raw["기준_날짜"]) + pd.to_timedelta(raw["시간대"], unit="h")

    agg = (
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
        .sort_values(["시작_대여소_ID", "datetime"])
    )

    stations = sorted(agg["시작_대여소_ID"].unique().tolist())
    full_time = pd.date_range(
        agg["datetime"].min().floor("D"),
        agg["datetime"].max().floor("D") + pd.Timedelta(hours=23),
        freq="h",
    )

    full_index = pd.MultiIndex.from_product(
        [full_time, stations],
        names=["datetime", "시작_대여소_ID"],
    ).to_frame(index=False)

    df = full_index.merge(agg, on=["datetime", "시작_대여소_ID"], how="left")
    df["전체_건수"] = df["전체_건수"].fillna(0.0)

    weather = (
        raw.groupby("datetime", as_index=False)[["온도", "습도", "불쾌지수", "강수량", "적설량"]]
        .mean()
        .sort_values("datetime")
    )
    weather = weather.set_index("datetime").reindex(full_time)
    weather = weather.interpolate(method="linear", limit_direction="both").ffill().bfill()
    weather = weather.reset_index().rename(columns={"index": "datetime"})
    df = df.drop(columns=["온도", "습도", "불쾌지수", "강수량", "적설량"]).merge(
        weather,
        on="datetime",
        how="left",
    )

    meta = load_station_meta(stations)
    df = df.merge(meta, on="시작_대여소_ID", how="left")

    df = df.sort_values(["시작_대여소_ID", "datetime"]).reset_index(drop=True)
    df["date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour
    df["weekday"] = df["datetime"].dt.dayofweek
    df["month"] = df["datetime"].dt.month
    df["dayofyear"] = df["datetime"].dt.dayofyear
    df["weekofyear"] = df["datetime"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["is_holiday"] = df["datetime"].dt.strftime("%Y-%m-%d").isin(KOREA_2024_HOLIDAYS).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["weekday_sin"] = np.sin(2 * np.pi * df["weekday"] / 7)
    df["weekday_cos"] = np.cos(2 * np.pi * df["weekday"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    station_group = df.groupby("시작_대여소_ID")["전체_건수"]
    df["lag_1h"] = station_group.shift(1)
    df["lag_2h"] = station_group.shift(2)
    df["lag_3h"] = station_group.shift(3)
    df["lag_24h"] = station_group.shift(24)
    df["lag_168h"] = station_group.shift(168)
    df["rolling_mean_3h"] = station_group.shift(1).rolling(3).mean()
    df["rolling_mean_6h"] = station_group.shift(1).rolling(6).mean()
    df["rolling_mean_24h"] = station_group.shift(1).rolling(24).mean()
    df["rolling_std_24h"] = station_group.shift(1).rolling(24).std()

    df["target"] = df["전체_건수"]
    df = df.dropna().reset_index(drop=True)
    return df


def fit_ridge_regression(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std == 0] = 1.0

    x_train_scaled = (x_train - mean) / std
    x_test_scaled = (x_test - mean) / std

    train_design = np.column_stack([np.ones(len(x_train_scaled)), x_train_scaled])
    test_design = np.column_stack([np.ones(len(x_test_scaled)), x_test_scaled])

    penalty = np.eye(train_design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coef = np.linalg.solve(train_design.T @ train_design + penalty, train_design.T @ y_train)
    pred = test_design @ coef
    return pred, mean, std


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    total = np.sum((y_true - np.mean(y_true)) ** 2)
    if total == 0:
        return 0.0
    return float(1 - np.sum((y_true - y_pred) ** 2) / total)


def run_model(
    input_path: Path,
    features_path: Path,
    predictions_path: Path,
    test_ratio: float,
    alpha: float,
) -> None:
    df = build_hourly_dataset(input_path)

    station_dummies = pd.get_dummies(df["시작_대여소_ID"], prefix="station", dtype=int)
    feature_df = pd.concat([df, station_dummies], axis=1)

    base_features = [
        "hour",
        "weekday",
        "month",
        "dayofyear",
        "weekofyear",
        "is_weekend",
        "is_holiday",
        "온도",
        "습도",
        "불쾌지수",
        "강수량",
        "적설량",
        "hour_sin",
        "hour_cos",
        "weekday_sin",
        "weekday_cos",
        "month_sin",
        "month_cos",
        "lag_1h",
        "lag_2h",
        "lag_3h",
        "lag_24h",
        "lag_168h",
        "rolling_mean_3h",
        "rolling_mean_6h",
        "rolling_mean_24h",
        "rolling_std_24h",
    ]

    optional_features = [col for col in ["위도", "경도", "cluster_12_custom", "연간_전체건수"] if col in feature_df.columns]
    feature_columns = base_features + optional_features + station_dummies.columns.tolist()

    feature_df[feature_columns] = feature_df[feature_columns].fillna(0.0)
    feature_df = feature_df.sort_values(["datetime", "시작_대여소_ID"]).reset_index(drop=True)
    feature_df.to_csv(features_path, index=False, encoding="utf-8-sig")

    split_idx = int(len(feature_df) * (1 - test_ratio))
    train = feature_df.iloc[:split_idx].copy()
    test = feature_df.iloc[split_idx:].copy()

    x_train = train[feature_columns].to_numpy(dtype=float)
    x_test = test[feature_columns].to_numpy(dtype=float)
    y_train = np.log1p(train["target"].to_numpy(dtype=float))
    y_test = test["target"].to_numpy(dtype=float)

    pred_log, _, _ = fit_ridge_regression(x_train, y_train, x_test, alpha=alpha)
    pred = np.expm1(pred_log)
    pred = np.clip(pred, 0.0, None)

    pred_df = test[["datetime", "시작_대여소_ID", "target"]].copy()
    pred_df["prediction"] = pred
    pred_df["abs_error"] = np.abs(pred_df["target"] - pred_df["prediction"])
    pred_df.to_csv(predictions_path, index=False, encoding="utf-8-sig")

    print(f"input_file={input_path}")
    print(f"feature_file={features_path}")
    print(f"prediction_file={predictions_path}")
    print(f"dataset_rows={len(feature_df)}")
    print(f"train_rows={len(train)}")
    print(f"test_rows={len(test)}")
    print(f"stations={feature_df['시작_대여소_ID'].nunique()}")
    print(f"train_start={train['datetime'].min()}")
    print(f"train_end={train['datetime'].max()}")
    print(f"test_start={test['datetime'].min()}")
    print(f"test_end={test['datetime'].max()}")
    print(f"feature_count={len(feature_columns)}")
    print("feature_columns=" + ",".join(feature_columns))
    print(f"MAE={mae(y_test, pred):.4f}")
    print(f"RMSE={rmse(y_test, pred):.4f}")
    print(f"R2={r2(y_test, pred):.4f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build station-hour features and evaluate a ridge model.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input CSV path")
    parser.add_argument("--features-out", type=Path, default=DEFAULT_FEATURES, help="Feature dataset CSV path")
    parser.add_argument(
        "--predictions-out",
        type=Path,
        default=DEFAULT_PREDICTIONS,
        help="Prediction result CSV path",
    )
    parser.add_argument("--test-ratio", type=float, default=0.2, help="Test split ratio")
    parser.add_argument("--alpha", type=float, default=3.0, help="Ridge regularization strength")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_model(
        input_path=args.input,
        features_path=args.features_out,
        predictions_path=args.predictions_out,
        test_ratio=args.test_ratio,
        alpha=args.alpha,
    )


if __name__ == "__main__":
    main()
