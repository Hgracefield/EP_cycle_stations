
from __future__ import annotations

import warnings
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import RandomizedSearchCV, GridSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import PolynomialFeatures
from sklearn.feature_selection import mutual_info_regression
from sklearn.ensemble import RandomForestRegressor

try:
    import optuna
except Exception:
    optuna = None

warnings.filterwarnings("ignore")

# =========================================================
# 0. 경로 설정
# =========================================================
DATA_PATH = Path("../../Data/sort_data/2024_data.parquet")
POP_PATH = Path("../../Data/pop_data.csv")
SUBWAY_RIDERSHIP_PATH = Path("../../Data/서울교통공사_역별_시간대별_승하차인원.csv")
# 아래 파일은 있으면 사용, 없으면 생략
SUBWAY_STATION_META_PATH = Path("../../Data/서울교통공사_역사좌표.csv")
STATION_META_PATH = Path("../../Data/station_meta.csv")
OUTPUT_DIR = Path("./outputs_bike_pipeline")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# =========================================================
# 1. 유틸
# =========================================================
def ensure_datetime(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    return df

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))

def safe_get_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def add_holiday_features(df: pd.DataFrame, date_col: str = "기준_날짜") -> pd.DataFrame:
    df = df.copy()
    # 한국 공휴일 라이브러리가 있으면 사용, 없으면 주말만 restingday로 설정
    try:
        import holidays
        kr_holidays = holidays.KR(years=sorted(df[date_col].dt.year.unique()))
        holiday_flag = df[date_col].dt.date.astype(object).isin(kr_holidays)
    except Exception:
        holiday_flag = pd.Series(False, index=df.index)

    weekday_num = df[date_col].dt.dayofweek  # Mon=0
    df["is_weekday"] = (weekday_num < 5).astype(int)
    df["is_restingday"] = ((weekday_num >= 5) | holiday_flag).astype(int)

    # 요청대로 원핫도 같이 생성
    weekday_ohe = pd.get_dummies(df["is_weekday"], prefix="is_weekday")
    resting_ohe = pd.get_dummies(df["is_restingday"], prefix="is_restingday")
    df = pd.concat([df, weekday_ohe, resting_ohe], axis=1)
    return df

def add_day_night_features(df: pd.DataFrame, hour_col: str = "hour") -> pd.DataFrame:
    df = df.copy()
    df["is_night"] = df[hour_col].isin([0,1,2,3,4,5,22,23]).astype(int)
    df["is_daytime"] = df[hour_col].between(6, 21).astype(int)

    night_ohe = pd.get_dummies(df["is_night"], prefix="is_night")
    daytime_ohe = pd.get_dummies(df["is_daytime"], prefix="is_daytime")
    df = pd.concat([df, night_ohe, daytime_ohe], axis=1)

    df["hour_business"] = df[hour_col].isin([8,9,10,11,12,13,14,15,16,17]).astype(int)
    df["hour_transit"] = df[hour_col].isin([7,8,9,17,18,19,20]).astype(int)
    return df

def add_weather_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rain_col = safe_get_col(df, ["강수량", "1시간강수량", "precipitation", "rainfall"])
    snow_col = safe_get_col(df, ["적설량", "snowfall", "snow_depth"])

    if rain_col:
        df["rain_flag"] = (pd.to_numeric(df[rain_col], errors="coerce").fillna(0) > 0).astype(int)
    else:
        df["rain_flag"] = 0

    if snow_col:
        df["snow_flag"] = (pd.to_numeric(df[snow_col], errors="coerce").fillna(0) > 0).astype(int)
    else:
        df["snow_flag"] = 0
    return df

def infer_target_col(df: pd.DataFrame) -> str:
    for c in ["전체_건수", "count", "target", "수요", "대여건수"]:
        if c in df.columns:
            return c
    raise ValueError("타깃 컬럼을 찾지 못했습니다. 예: 전체_건수")

def numeric_feature_list(df: pd.DataFrame, target_col: str, exclude: List[str]) -> List[str]:
    cols = []
    for c in df.columns:
        if c in exclude or c == target_col:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols

def plot_feature_vs_target(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    outdir: Path,
    max_features: int = 24,
):
    outdir.mkdir(exist_ok=True, parents=True)
    selected = feature_cols[:max_features]
    for col in selected:
        fig = plt.figure(figsize=(7, 4))
        plt.scatter(df[col], df[target_col], s=10, alpha=0.35)
        plt.title(f"{col} vs {target_col}")
        plt.xlabel(col)
        plt.ylabel(target_col)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(outdir / f"scatter_{col}.png", dpi=150)
        plt.close(fig)

def compare_raw_log_poly(
    df: pd.DataFrame, feature_cols: List[str], target_col: str, outdir: Path
) -> pd.DataFrame:
    """
    month/day/hour 제외, 각 feature에 대해
    raw / log1p / poly2 가 target과 어떤 관계를 갖는지 간단 비교.
    수치 기준: |pearson| 와 mutual information
    """
    records = []
    for col in feature_cols:
        if col in ["month", "day", "hour"]:
            continue

        x = pd.to_numeric(df[col], errors="coerce")
        y = pd.to_numeric(df[target_col], errors="coerce")
        valid = x.notna() & y.notna()
        if valid.sum() < 30:
            continue

        x0 = x[valid].to_numpy().reshape(-1, 1)
        y0 = y[valid].to_numpy()

        raw_abs_corr = abs(pd.Series(x0.ravel()).corr(pd.Series(y0)))
        raw_mi = mutual_info_regression(x0, y0, random_state=42)[0]

        if (x0 >= 0).all():
            x_log = np.log1p(x0)
            log_abs_corr = abs(pd.Series(x_log.ravel()).corr(pd.Series(y0)))
            log_mi = mutual_info_regression(x_log, y0, random_state=42)[0]
        else:
            log_abs_corr, log_mi = np.nan, np.nan

        poly = PolynomialFeatures(degree=2, include_bias=False)
        x_poly = poly.fit_transform(x0)
        poly_mi = mutual_info_regression(x_poly, y0, random_state=42).sum()
        poly_abs_corr = max(
            abs(pd.Series(x_poly[:, i]).corr(pd.Series(y0))) for i in range(x_poly.shape[1])
        )

        best = pd.Series({
            "raw": np.nanmean([raw_abs_corr, raw_mi]),
            "log1p": np.nanmean([log_abs_corr, log_mi]),
            "poly2": np.nanmean([poly_abs_corr, poly_mi]),
        }).idxmax()

        records.append({
            "feature": col,
            "raw_abs_corr": raw_abs_corr,
            "raw_mi": raw_mi,
            "log_abs_corr": log_abs_corr,
            "log_mi": log_mi,
            "poly_abs_corr": poly_abs_corr,
            "poly_mi": poly_mi,
            "best_transform": best,
        })

        # 시각화
        fig = plt.figure(figsize=(12, 3.6))
        plt.subplot(1, 3, 1)
        plt.scatter(x0, y0, s=8, alpha=0.25)
        plt.title(f"{col} raw")

        plt.subplot(1, 3, 2)
        if (x0 >= 0).all():
            plt.scatter(np.log1p(x0), y0, s=8, alpha=0.25)
            plt.title(f"{col} log1p")
        else:
            plt.text(0.5, 0.5, "negative exists", ha="center", va="center")
            plt.title(f"{col} log1p skip")

        plt.subplot(1, 3, 3)
        plt.scatter(x0**2, y0, s=8, alpha=0.25)
        plt.title(f"{col} poly2(x^2)")
        plt.tight_layout()
        plt.savefig(outdir / f"transform_compare_{col}.png", dpi=150)
        plt.close(fig)

    res = pd.DataFrame(records).sort_values(["best_transform", "raw_mi"], ascending=[True, False])
    res.to_csv(outdir / "feature_transform_comparison.csv", index=False, encoding="utf-8-sig")
    return res

def apply_feature_transforms(df: pd.DataFrame, transform_df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for _, row in transform_df.iterrows():
        col = row["feature"]
        best = row["best_transform"]
        if col not in df.columns:
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        if best == "log1p" and (x.dropna() >= 0).all():
            df[f"{col}_log1p"] = np.log1p(x)
        elif best == "poly2":
            df[f"{col}_sq"] = x ** 2
    return df

def add_subway_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    station_meta + subway station meta + ridership가 모두 있을 때만 사용.
    없으면 조용히 스킵.
    """
    if not (STATION_META_PATH.exists() and SUBWAY_STATION_META_PATH.exists() and SUBWAY_RIDERSHIP_PATH.exists()):
        print("[INFO] 지하철 관련 보조 파일이 부족하여 subway feature 단계는 skip합니다.")
        for c in ["near_subway_200m", "commute_peak_in", "commute_peak_out", "is_airport_rail", "is_ktx"]:
            df[c] = 0
        return df

    bike_meta = pd.read_csv(STATION_META_PATH)
    subway_meta = pd.read_csv(SUBWAY_STATION_META_PATH)
    ridership = pd.read_csv(SUBWAY_RIDERSHIP_PATH)

    bike_id_col = safe_get_col(bike_meta, ["대여소_ID", "시작_대여소_ID", "station_id"])
    bike_lat_col = safe_get_col(bike_meta, ["위도", "lat", "latitude"])
    bike_lon_col = safe_get_col(bike_meta, ["경도", "lon", "longitude"])
    sub_name_col = safe_get_col(subway_meta, ["역명", "station_name"])
    sub_lat_col = safe_get_col(subway_meta, ["위도", "lat", "latitude"])
    sub_lon_col = safe_get_col(subway_meta, ["경도", "lon", "longitude"])
    line_col = safe_get_col(subway_meta, ["호선명", "line", "노선명"])

    rider_name_col = safe_get_col(ridership, ["역명", "station_name"])
    hour_col = safe_get_col(ridership, ["시간대", "hour"])
    in_col = safe_get_col(ridership, ["승차인원", "승차", "in_cnt"])
    out_col = safe_get_col(ridership, ["하차인원", "하차", "out_cnt"])

    if None in [bike_id_col, bike_lat_col, bike_lon_col, sub_name_col, sub_lat_col, sub_lon_col]:
        print("[INFO] 지하철/대여소 좌표 컬럼명이 예상과 달라 subway feature 단계는 skip합니다.")
        for c in ["near_subway_200m", "commute_peak_in", "commute_peak_out", "is_airport_rail", "is_ktx"]:
            df[c] = 0
        return df

    # 자전거 대여소별 가장 가까운 지하철역 찾기
    pairs = []
    for _, b in bike_meta[[bike_id_col, bike_lat_col, bike_lon_col]].drop_duplicates().iterrows():
        tmp = subway_meta[[sub_name_col, sub_lat_col, sub_lon_col] + ([line_col] if line_col else [])].copy()
        tmp["dist_m"] = haversine_m(
            b[bike_lat_col], b[bike_lon_col],
            tmp[sub_lat_col].values, tmp[sub_lon_col].values
        )
        row = tmp.sort_values("dist_m").iloc[0].to_dict()
        row[bike_id_col] = b[bike_id_col]
        pairs.append(row)
    near_df = pd.DataFrame(pairs)

    near_df["near_subway_200m"] = (near_df["dist_m"] <= 200).astype(int)

    if rider_name_col and hour_col and in_col and out_col:
        ridership[hour_col] = pd.to_numeric(ridership[hour_col], errors="coerce")
        in_peak = ridership[ridership[hour_col].isin([7,8,9])].groupby(rider_name_col)[in_col].mean().rename("commute_peak_in")
        out_peak = ridership[ridership[hour_col].isin([17,18,19,20])].groupby(rider_name_col)[out_col].mean().rename("commute_peak_out")
        near_df = near_df.merge(in_peak, left_on=sub_name_col, right_index=True, how="left")
        near_df = near_df.merge(out_peak, left_on=sub_name_col, right_index=True, how="left")
    else:
        near_df["commute_peak_in"] = np.nan
        near_df["commute_peak_out"] = np.nan

    if line_col:
        near_df["is_airport_rail"] = near_df[line_col].astype(str).str.contains("공항", na=False).astype(int)
        near_df["is_ktx"] = near_df[line_col].astype(str).str.contains("KTX", na=False).astype(int)
    else:
        near_df["is_airport_rail"] = 0
        near_df["is_ktx"] = 0

    join_key = "시작_대여소_ID" if "시작_대여소_ID" in df.columns else bike_id_col
    near_df = near_df.rename(columns={bike_id_col: join_key})
    keep_cols = [join_key, "near_subway_200m", "commute_peak_in", "commute_peak_out", "is_airport_rail", "is_ktx"]
    df = df.merge(near_df[keep_cols], on=join_key, how="left")

    fill_cols = ["near_subway_200m", "commute_peak_in", "commute_peak_out", "is_airport_rail", "is_ktx"]
    for c in fill_cols:
        df[c] = df[c].fillna(0)
    return df

def add_pop_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    pop_data.csv 구조를 모르므로 가능한 컬럼명 후보 기반으로 조인.
    station 좌표 메타파일이 없으면 skip.
    """
    if not (POP_PATH.exists() and STATION_META_PATH.exists()):
        print("[INFO] pop/station_meta 파일이 부족하여 pop feature 단계는 skip합니다.")
        for c in [
            "business_ratio", "business_index", "residential_ratio", "residential_index",
            "transit_ratio", "transit_index", "leisure_ratio", "leisure_index",
            "commute_ratio", "commute_index"
        ]:
            df[c] = np.nan
        return df

    pop = pd.read_csv(POP_PATH)
    station_meta = pd.read_csv(STATION_META_PATH)

    # 가장 쉬운 경우: 이미 대여소_ID 기준 feature가 있을 때
    id_col = safe_get_col(pop, ["대여소_ID", "station_id", "시작_대여소_ID"])
    if id_col:
        join_key = "시작_대여소_ID" if "시작_대여소_ID" in df.columns else id_col
        pop = pop.rename(columns={id_col: join_key})
        keep = [join_key] + [c for c in pop.columns if c != join_key]
        return df.merge(pop[keep], on=join_key, how="left")

    # 좌표 기반 최근접 매칭 시도
    st_id = safe_get_col(station_meta, ["대여소_ID", "시작_대여소_ID", "station_id"])
    st_lat = safe_get_col(station_meta, ["위도", "lat", "latitude"])
    st_lon = safe_get_col(station_meta, ["경도", "lon", "longitude"])
    pp_lat = safe_get_col(pop, ["위도", "lat", "latitude"])
    pp_lon = safe_get_col(pop, ["경도", "lon", "longitude"])

    feature_candidates = [
        "business_ratio", "business_index", "residential_ratio", "residential_index",
        "transit_ratio", "transit_index", "leisure_ratio", "leisure_index",
        "commute_ratio", "commute_index"
    ]
    present_feats = [c for c in feature_candidates if c in pop.columns]

    if None in [st_id, st_lat, st_lon, pp_lat, pp_lon] or not present_feats:
        print("[INFO] pop_data 컬럼이 예상과 달라 pop feature 단계는 skip합니다.")
        for c in feature_candidates:
            if c not in df.columns:
                df[c] = np.nan
        return df

    rows = []
    for _, s in station_meta[[st_id, st_lat, st_lon]].drop_duplicates().iterrows():
        tmp = pop[[pp_lat, pp_lon] + present_feats].copy()
        tmp["dist_m"] = haversine_m(
            s[st_lat], s[st_lon],
            tmp[pp_lat].values, tmp[pp_lon].values
        )
        near = tmp[tmp["dist_m"] <= 200]
        row = {st_id: s[st_id]}
        for f in present_feats:
            row[f] = near[f].mean() if len(near) else np.nan
        rows.append(row)
    feat_df = pd.DataFrame(rows)

    join_key = "시작_대여소_ID" if "시작_대여소_ID" in df.columns else st_id
    feat_df = feat_df.rename(columns={st_id: join_key})
    return df.merge(feat_df, on=join_key, how="left")

def split_train_valid_test(df: pd.DataFrame, date_col: str = "기준_날짜") -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[df[date_col] < "2024-11-01"].copy()
    valid = df[(df[date_col] >= "2024-11-01") & (df[date_col] < "2024-12-01")].copy()
    test = df[df[date_col] >= "2024-12-01"].copy()
    return train, valid, test

def add_lag_rolling_features(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """
    station + datetime 정렬 후 과거 정보만 사용.
    shift를 반드시 먼저 적용.
    """
    df = df.copy()
    date_col = "기준_날짜"
    station_col = "시작_대여소_ID" if "시작_대여소_ID" in df.columns else None
    dt_col = "datetime"

    if dt_col not in df.columns:
        df[dt_col] = pd.to_datetime(df[date_col]) + pd.to_timedelta(df["hour"], unit="h")

    sort_cols = [station_col, dt_col] if station_col else [dt_col]
    df = df.sort_values(sort_cols).copy()

    group_obj = df.groupby(station_col) if station_col else [(None, df)]

    def _make(group: pd.DataFrame) -> pd.DataFrame:
        s = group[target_col]
        group["lag_1hr"] = s.shift(1)
        group["lag_2hr"] = s.shift(2)
        group["lag_3hr"] = s.shift(3)
        group["lag_24hr"] = s.shift(24)
        group["lag_168hr"] = s.shift(168)

        shifted = s.shift(1)
        group["rolling_mean_3hr"] = shifted.rolling(3).mean()
        group["rolling_mean_6hr"] = shifted.rolling(6).mean()
        group["rolling_mean_24hr"] = shifted.rolling(24).mean()
        group["rolling_std_24hr"] = shifted.rolling(24).std()
        return group

    if station_col:
        df = group_obj.apply(_make).reset_index(drop=True)
    else:
        df = _make(df)
    return df

def prepare_xy(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    target_col: str,
    drop_cols: List[str],
):
    feature_cols = [c for c in train.columns if c not in drop_cols + [target_col]]
    # train 기준으로 숫자/더미만 사용
    usable = []
    for c in feature_cols:
        if pd.api.types.is_numeric_dtype(train[c]):
            usable.append(c)

    X_train = train[usable].copy()
    X_valid = valid[usable].copy()
    X_test = test[usable].copy()

    y_train = train[target_col].copy()
    y_valid = valid[target_col].copy()
    y_test = test[target_col].copy()

    # 학습/예측 모델 편의를 위해 NaN은 그대로 두되,
    # RandomForestRegressor가 NaN 처리 안 될 수 있어 단순 대치
    med = X_train.median(numeric_only=True)
    X_train = X_train.fillna(med)
    X_valid = X_valid.fillna(med)
    X_test = X_test.fillna(med)

    return X_train, y_train, X_valid, y_valid, X_test, y_test, usable

def get_sample_weights(df: pd.DataFrame) -> np.ndarray:
    w = np.ones(len(df), dtype=float)
    if "hour" in df.columns:
        w += np.where(df["hour"].isin([7,8,9]), 0.5, 0.0)
        w += np.where(df["hour"].isin([17,18,19,20]), 0.5, 0.0)
    return w

def eval_regression(y_true, y_pred) -> Dict[str, float]:
    rmse = mean_squared_error(y_true, y_pred) ** 0.5
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": rmse,
        "R2": r2_score(y_true, y_pred),
    }

def plot_predictions(y_true, y_pred, title_prefix: str, outdir: Path):
    # scatter
    fig = plt.figure(figsize=(5, 5))
    plt.scatter(y_true, y_pred, s=10, alpha=0.35)
    mn = min(np.min(y_true), np.min(y_pred))
    mx = max(np.max(y_true), np.max(y_pred))
    plt.plot([mn, mx], [mn, mx])
    plt.xlabel("Actual")
    plt.ylabel("Predicted")
    plt.title(f"{title_prefix} Scatter")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / f"{title_prefix}_scatter.png", dpi=150)
    plt.close(fig)

    # residual
    residual = y_true - y_pred
    fig = plt.figure(figsize=(6, 4))
    plt.scatter(y_pred, residual, s=10, alpha=0.35)
    plt.axhline(0, linestyle="--")
    plt.xlabel("Predicted")
    plt.ylabel("Residual")
    plt.title(f"{title_prefix} Residual")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / f"{title_prefix}_residual.png", dpi=150)
    plt.close(fig)

    # sample plot
    n = min(300, len(y_true))
    fig = plt.figure(figsize=(12, 4))
    plt.plot(np.arange(n), np.asarray(y_true)[:n], label="actual")
    plt.plot(np.arange(n), np.asarray(y_pred)[:n], label="pred")
    plt.title(f"{title_prefix} Sample Plot (first {n})")
    plt.xlabel("Index")
    plt.ylabel("Target")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / f"{title_prefix}_sample.png", dpi=150)
    plt.close(fig)

def feature_selection_report(X_train: pd.DataFrame, y_train: pd.Series, outdir: Path) -> pd.DataFrame:
    # 1) RandomForest importance
    base = RandomForestRegressor(
        n_estimators=300, max_depth=12, min_samples_leaf=2, random_state=42, n_jobs=-1
    )
    base.fit(X_train, y_train)
    imp = pd.DataFrame({
        "feature": X_train.columns,
        "rf_importance": base.feature_importances_,
    })

    # 2) 결측/상수/중복상관
    nunique = X_train.nunique(dropna=False)
    stats = pd.DataFrame({
        "feature": X_train.columns,
        "nunique": [nunique[c] for c in X_train.columns],
        "missing_ratio": [X_train[c].isna().mean() for c in X_train.columns],
        "zero_ratio": [(X_train[c] == 0).mean() if pd.api.types.is_numeric_dtype(X_train[c]) else np.nan for c in X_train.columns],
    })

    corr = X_train.corr(numeric_only=True).abs()
    high_corr_map = {}
    for c in corr.columns:
        vals = corr[c].drop(c, errors="ignore")
        high_corr_map[c] = vals[vals >= 0.95].index.tolist()
    stats["high_corr_partners"] = stats["feature"].map(high_corr_map)

    report = stats.merge(imp, on="feature", how="left").sort_values("rf_importance")
    report["drop_must"] = (
        (report["nunique"] <= 1) |
        ((report["rf_importance"].fillna(0) < 0.001) & (report["missing_ratio"] >= 0.9))
    )
    report["drop_consider"] = (
        (~report["drop_must"]) &
        (
            (report["rf_importance"].fillna(0) < 0.003) |
            (report["high_corr_partners"].apply(lambda x: len(x) if isinstance(x, list) else 0) >= 1)
        )
    )

    report.to_csv(outdir / "feature_selection_report.csv", index=False, encoding="utf-8-sig")

    # 시각화
    top = report.sort_values("rf_importance", ascending=False).head(30)
    fig = plt.figure(figsize=(8, 10))
    plt.barh(top["feature"][::-1], top["rf_importance"][::-1])
    plt.title("Feature Importance (base RF)")
    plt.tight_layout()
    plt.savefig(outdir / "feature_importance_base_rf.png", dpi=150)
    plt.close(fig)

    return report

def run_random_search(X_train, y_train, sample_weight, tscv):
    model = RandomForestRegressor(random_state=42, n_jobs=-1)
    param_dist = {
        "n_estimators": [200, 300, 500, 700],
        "max_depth": [8, 10, 12, 16, None],
        "min_samples_split": [2, 5, 10, 20],
        "min_samples_leaf": [1, 2, 4, 8],
        "max_features": ["sqrt", "log2", 0.7, 1.0],
    }
    search = RandomizedSearchCV(
        model,
        param_distributions=param_dist,
        n_iter=20,
        scoring="neg_mean_absolute_error",
        cv=tscv,
        random_state=42,
        n_jobs=-1,
        verbose=1,
    )
    search.fit(X_train, y_train, sample_weight=sample_weight)
    return search

def run_grid_search(X_train, y_train, sample_weight, tscv):
    model = RandomForestRegressor(random_state=42, n_jobs=-1)
    param_grid = {
        "n_estimators": [300, 500],
        "max_depth": [10, 16, None],
        "min_samples_split": [2, 5],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", 0.7],
    }
    search = GridSearchCV(
        model,
        param_grid=param_grid,
        scoring="neg_mean_absolute_error",
        cv=tscv,
        n_jobs=-1,
        verbose=1,
    )
    search.fit(X_train, y_train, sample_weight=sample_weight)
    return search

def run_optuna_search(X_train, y_train, sample_weight, tscv, n_trials=30):
    if optuna is None:
        print("[INFO] optuna 미설치 -> optuna 단계 skip")
        return None

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 200, 800, step=100),
            "max_depth": trial.suggest_categorical("max_depth", [8, 10, 12, 16, 20, None]),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 8),
            "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", 0.7, 1.0]),
            "random_state": 42,
            "n_jobs": -1,
        }
        maes = []
        for tr_idx, va_idx in tscv.split(X_train):
            X_tr, X_va = X_train.iloc[tr_idx], X_train.iloc[va_idx]
            y_tr, y_va = y_train.iloc[tr_idx], y_train.iloc[va_idx]
            sw_tr = sample_weight[tr_idx]
            m = RandomForestRegressor(**params)
            m.fit(X_tr, y_tr, sample_weight=sw_tr)
            pred = m.predict(X_va)
            maes.append(mean_absolute_error(y_va, pred))
        return np.mean(maes)

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study

def plot_search_results(random_search, grid_search, optuna_study, outdir: Path):
    if random_search is not None:
        cvres = pd.DataFrame(random_search.cv_results_).sort_values("rank_test_score")
        fig = plt.figure(figsize=(7, 4))
        plt.plot(-cvres["mean_test_score"].reset_index(drop=True))
        plt.title("Random Search CV Score Trend (MAE lower is better)")
        plt.xlabel("ranked candidate")
        plt.ylabel("CV MAE")
        plt.tight_layout()
        plt.savefig(outdir / "random_search_cv_trend.png", dpi=150)
        plt.close(fig)

    if grid_search is not None:
        cvres = pd.DataFrame(grid_search.cv_results_).sort_values("rank_test_score")
        fig = plt.figure(figsize=(7, 4))
        plt.plot(-cvres["mean_test_score"].reset_index(drop=True))
        plt.title("Grid Search CV Score Trend (MAE lower is better)")
        plt.xlabel("ranked candidate")
        plt.ylabel("CV MAE")
        plt.tight_layout()
        plt.savefig(outdir / "grid_search_cv_trend.png", dpi=150)
        plt.close(fig)

    if optuna_study is not None:
        vals = [t.value for t in optuna_study.trials if t.value is not None]
        fig = plt.figure(figsize=(7, 4))
        plt.plot(vals)
        plt.title("Optuna Trial MAE Trend")
        plt.xlabel("trial")
        plt.ylabel("CV MAE")
        plt.tight_layout()
        plt.savefig(outdir / "optuna_trial_trend.png", dpi=150)
        plt.close(fig)

def choose_best_model(random_search, grid_search, optuna_study, X_train, y_train, sample_weight):
    candidates = []

    if random_search is not None:
        candidates.append(("random", -random_search.best_score_, random_search.best_params_))
    if grid_search is not None:
        candidates.append(("grid", -grid_search.best_score_, grid_search.best_params_))
    if optuna_study is not None:
        best_params = optuna_study.best_trial.params.copy()
        candidates.append(("optuna", optuna_study.best_value, best_params))

    candidates = sorted(candidates, key=lambda x: x[1])
    best_name, best_cv_mae, best_params = candidates[0]

    best_params = best_params.copy()
    best_params.update({"random_state": 42, "n_jobs": -1})
    model = RandomForestRegressor(**best_params)
    model.fit(X_train, y_train, sample_weight=sample_weight)
    return best_name, best_cv_mae, best_params, model

# =========================================================
# 2. 데이터 로드
# =========================================================
print("[STEP] load parquet")
df = pd.read_parquet(DATA_PATH)
print("raw shape:", df.shape)
print("columns:", df.columns.tolist())

# 날짜 컬럼/시간대 컬럼 표준화
date_col = safe_get_col(df, ["기준_날짜", "date", "대여일자", "일자"])
if date_col is None:
    raise ValueError("기준 날짜 컬럼을 찾지 못했습니다.")
if date_col != "기준_날짜":
    df = df.rename(columns={date_col: "기준_날짜"})
df = ensure_datetime(df, "기준_날짜")

hour_col = safe_get_col(df, ["시간대", "hour", "기준_시간대"])
if hour_col is None:
    raise ValueError("시간대 컬럼을 찾지 못했습니다.")
if hour_col != "hour":
    df = df.rename(columns={hour_col: "hour"})

target_col = infer_target_col(df)

# 기본 파생
df["month"] = df["기준_날짜"].dt.month
df["day"] = df["기준_날짜"].dt.day
df["datetime"] = df["기준_날짜"] + pd.to_timedelta(df["hour"], unit="h")

# =========================================================
# 3. 전처리
# =========================================================
print("[STEP] basic filtering")
use_min_col = safe_get_col(df, ["전체_이용_분", "이용분", "duration_min"])
dist_col = safe_get_col(df, ["전체_이용_거리", "이용거리", "distance"])
end_station_col = safe_get_col(df, ["종료_대여소_ID", "end_station_id"])

if end_station_col:
    df = df.drop(columns=[end_station_col])

if use_min_col:
    df = df[pd.to_numeric(df[use_min_col], errors="coerce") > 5]
if dist_col:
    df = df[pd.to_numeric(df[dist_col], errors="coerce") > 0]

# weekday/holiday
df = add_holiday_features(df, "기준_날짜")

# day/night/business/transit/rain/snow
df = add_day_night_features(df, "hour")
df = add_weather_flags(df)

# 보조 feature
print("[STEP] auxiliary joins")
df = add_subway_features(df)
df = add_pop_features(df)

# station one-hot (시작 대여소)
station_col = safe_get_col(df, ["시작_대여소_ID", "start_station_id"])
if station_col and station_col != "시작_대여소_ID":
    df = df.rename(columns={station_col: "시작_대여소_ID"})
if "시작_대여소_ID" in df.columns:
    station_ohe = pd.get_dummies(df["시작_대여소_ID"], prefix="station")
    df = pd.concat([df, station_ohe], axis=1)

print("after preprocess shape:", df.shape)

# =========================================================
# 4. feature vs target 비교 / transform 판단
# =========================================================
print("[STEP] transform comparison")
exclude_for_cmp = ["기준_날짜", "datetime", target_col]
num_cols_for_cmp = numeric_feature_list(df, target_col, exclude_for_cmp)
transform_dir = OUTPUT_DIR / "feature_transform_plots"
transform_dir.mkdir(exist_ok=True, parents=True)

transform_df = compare_raw_log_poly(df, num_cols_for_cmp, target_col, transform_dir)
print(transform_df.head(20))

df = apply_feature_transforms(df, transform_df)

# =========================================================
# 5. 시계열 split
# =========================================================
print("[STEP] split")
train_df, valid_df, test_df = split_train_valid_test(df, "기준_날짜")
print("train:", train_df.shape, "valid:", valid_df.shape, "test:", test_df.shape)

# =========================================================
# 6. lag / rolling (반드시 shift 사용)
# train+valid+test 전체에서 과거 방향으로 생성 후 split 유지
# =========================================================
print("[STEP] lag/rolling")
df_full = add_lag_rolling_features(df, target_col)

train_df = df_full[df_full["기준_날짜"] < "2024-11-01"].copy()
valid_df = df_full[(df_full["기준_날짜"] >= "2024-11-01") & (df_full["기준_날짜"] < "2024-12-01")].copy()
test_df = df_full[df_full["기준_날짜"] >= "2024-12-01"].copy()

# =========================================================
# 7. feature selection
# =========================================================
print("[STEP] feature selection")
drop_cols = ["기준_날짜", "datetime"]
X_train0, y_train0, X_valid0, y_valid0, X_test0, y_test0, usable0 = prepare_xy(
    train_df, valid_df, test_df, target_col, drop_cols
)
fs_report = feature_selection_report(X_train0, y_train0, OUTPUT_DIR)
print(fs_report.head(20))

drop_must = fs_report.loc[fs_report["drop_must"], "feature"].tolist()
drop_consider = fs_report.loc[fs_report["drop_consider"], "feature"].tolist()

print("\n[삭제 필수 후보]")
print(drop_must[:50])

print("\n[삭제 고려 후보]")
print(drop_consider[:50])

# 삭제 필수만 우선 제거
drop_cols_final = drop_cols + drop_must
X_train, y_train, X_valid, y_valid, X_test, y_test, usable = prepare_xy(
    train_df, valid_df, test_df, target_col, drop_cols_final
)

# =========================================================
# 8. 하이퍼파라미터 튜닝 (가중치 포함)
# =========================================================
print("[STEP] hyperparameter tuning")
sample_weight = get_sample_weights(train_df.loc[X_train.index])
tscv = TimeSeriesSplit(n_splits=4)

random_search = run_random_search(X_train, y_train, sample_weight, tscv)
grid_search = run_grid_search(X_train, y_train, sample_weight, tscv)
optuna_study = run_optuna_search(X_train, y_train, sample_weight, tscv, n_trials=30)

plot_search_results(random_search, grid_search, optuna_study, OUTPUT_DIR)

# =========================================================
# 9. 최적 모델 선택 및 valid 평가
# =========================================================
print("[STEP] choose best model")
best_name, best_cv_mae, best_params, best_model = choose_best_model(
    random_search, grid_search, optuna_study, X_train, y_train, sample_weight
)

print("best search:", best_name)
print("best cv mae:", best_cv_mae)
print("best params:", best_params)

valid_pred = best_model.predict(X_valid)
valid_metrics = eval_regression(y_valid, valid_pred)
print("\n[VALID METRICS]")
print(valid_metrics)

test_pred = best_model.predict(X_test)
test_metrics = eval_regression(y_test, test_pred)
print("\n[TEST METRICS]")
print(test_metrics)

# =========================================================
# 10. 중요도 시각화
# =========================================================
fi = pd.DataFrame({
    "feature": X_train.columns,
    "importance": best_model.feature_importances_,
}).sort_values("importance", ascending=False)

fi.to_csv(OUTPUT_DIR / "best_model_feature_importance.csv", index=False, encoding="utf-8-sig")

fig = plt.figure(figsize=(8, 10))
topk = fi.head(30).sort_values("importance")
plt.barh(topk["feature"], topk["importance"])
plt.title("Best Model Feature Importance Top 30")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "best_model_feature_importance_top30.png", dpi=150)
plt.close(fig)

# =========================================================
# 11. 결과 시각화
# =========================================================
plot_predictions(y_valid, valid_pred, "valid", OUTPUT_DIR)
plot_predictions(y_test, test_pred, "test", OUTPUT_DIR)

# commute hour 성능만 별도
if "hour" in valid_df.columns:
    commute_mask = valid_df.loc[X_valid.index, "hour"].isin([7,8,9,17,18,19,20]).values
    if commute_mask.sum() > 0:
        commute_metrics = eval_regression(y_valid[commute_mask], valid_pred[commute_mask])
        print("\n[VALID COMMUTE METRICS]")
        print(commute_metrics)

# =========================================================
# 12. 요약 저장
# =========================================================
summary = pd.DataFrame([
    {"split": "valid", **valid_metrics},
    {"split": "test", **test_metrics},
])
summary.to_csv(OUTPUT_DIR / "metrics_summary.csv", index=False, encoding="utf-8-sig")

print("\n완료.")
print("산출물 폴더:", OUTPUT_DIR.resolve())
print("- feature_transform_comparison.csv")
print("- feature_selection_report.csv")
print("- best_model_feature_importance.csv")
print("- metrics_summary.csv")
print("- 각종 scatter / residual / sample / search trend 이미지")
