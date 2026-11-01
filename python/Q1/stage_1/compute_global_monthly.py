# -*- coding: utf-8 -*-
"""Q1 建模阶段 stage_1：按月计算全球平均气温序列。

【为什么两种口径并列】
  100 个观测点在地球上分布不均（中低纬、欧美偏密），直接算术平均会让"站点多的地方"
  主导结果。故同时输出两种口径，两列之差即为"站点分布偏置"的量级，可作口径稳健性证据：
    equal  : 城市等权算术平均                     -> gmean_equal
    coslat : 按 cos(纬度) 加权（球面等面积近似）   -> gmean_coslat

【为什么从 1891 年开始】
  1891 年起 100 个观测点全部有数；1743-1890 站点数从 13 涨到 99，站点数增长会被误读成
  气温变化。窗口起止在 config.json 的 global.window 里改。

【取值策略（global.value_policy.mode）】——决定每行取哪一列气温
  tmean : 用合并阶段判定的最终值（默认）。1891-2013 主体是附件、2014 起是 POWER，
          前后不同源，会在 2014 年初带一个约 -0.5 ℃ 的台阶。
  att   : 只用附件原值 att_value。同源无台阶，但附件 2013-09 后断供，序列止于 2013-09。
  power : 只用 POWER 值 power_value。一直覆盖到 2022-12，但 POWER 从 1991 起才有。

【POWER 偏差修正（global.value_policy.power_bias_correction）】——消除跨源台阶
  none     : 不修正。
  global   : 用重叠期 mean(att_value - power_value) 作为全局常数（实测约 +0.53 ℃），
             只抬升取自 POWER 的行。
  per_city : 每个城市各用自己的重叠期均值偏差，再把缺失城市退回全局均值。

【输入】
  output/Q1/merged_city_monthly_1743_2022.csv
  预处理步骤2 的合并结果（uid, lat, date, tmean, source, att_value, power_value）

【输出】（result/Q1/，日志进 log/Q1/）
  global_monthly_tmean_1891_2022.csv   逐月全球平均气温（两口径并列）

【用法】
  python python/Q1/stage_1/compute_global_monthly.py
  python python/Q1/stage_1/compute_global_monthly.py --config python/Q1/stage_1/config.json
  python python/Q1/stage_1/compute_global_monthly.py --mode att            # 只用附件
  python python/Q1/stage_1/compute_global_monthly.py --mode power          # 只用 POWER
  python python/Q1/stage_1/compute_global_monthly.py --power-bias global   # 抬平跨源台阶

【可调参数】
  global.window.start / end              聚合窗口（默认 1891-01 ~ 2022-12）
  global.value_policy.mode               取值列（tmean / att / power）
  global.value_policy.power_bias_correction  POWER 偏差修正（none / global / per_city）
  global.weights.equal/coslat            两口径开关；只开一种就只输出一列
  global.decimals                        输出小数位（默认 3，与 tmean 精度一致）
  global.output_file                     结果文件名
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # -> python/Q1

from common.model_utils import (  # noqa: E402
    load_json, resolve_path, save_csv, setup_logger,
)

DEFAULT_CONFIG = "python/Q1/stage_1/config.json"
LOG_NAME = "stage_1_global_monthly.log"

VALUE_COL = "value"              # 聚合实际使用的列，由取值策略生成
MERGED_VALUE_COL = "tmean"       # 合并阶段判定的最终值（默认策略直接用）
ATT_COL = "att_value"            # 附件原值
POWER_COL = "power_value"        # POWER 原值
SOURCE_COL = "source"
MONTH_COL = "month"              # 内部用 Period 月，避免日期补零问题
COUNT_COL = "n_cities"
DATE_COL = "date"

# tmean 列取自 POWER 的两类 source（其余取自附件），POWER 偏差修正只作用在这两类上
POWER_SOURCES = ("power_replace", "power_fill")
VALUE_MODES = ("tmean", "att", "power")
BIAS_MODES = ("none", "global", "per_city")

# 口径登记表：config 的开关名 -> (临时权重列, 输出列名)。新增口径只需在这里加一行
WEIGHT_SPECS: dict[str, dict[str, str]] = {
    "equal": {"weight": "w_equal", "output": "gmean_equal", "label": "城市等权"},
    "coslat": {"weight": "w_coslat", "output": "gmean_coslat", "label": "cos(纬度) 面积加权"},
}


# --------------------------------------------------------------------------- #
# 读入与校验
# --------------------------------------------------------------------------- #
def load_merged(cfg: dict, logger) -> pd.DataFrame:
    """读入逐月长表并裁到窗口期，返回原始三列气温（tmean/att/power）与来源标记。"""
    path = resolve_path(cfg["paths"]["input_csv"])
    if not path.is_file():
        raise FileNotFoundError(f"未找到合并结果: {path}（先运行预处理 script/Q1/merge_city_monthly.py）")

    window = cfg["global"]["window"]
    start, end = pd.Period(window["start"], "M"), pd.Period(window["end"], "M")

    keep = ["uid", "lat", DATE_COL, MERGED_VALUE_COL, SOURCE_COL, ATT_COL, POWER_COL]
    frame = pd.read_csv(path, usecols=keep)
    frame[DATE_COL] = pd.to_datetime(frame[DATE_COL])
    frame[MONTH_COL] = frame[DATE_COL].dt.to_period("M")
    frame = frame[frame[MONTH_COL].between(start, end)].copy()
    if frame.empty:
        raise ValueError(f"窗口 {start} ~ {end} 内没有数据，请检查 global.window")

    frame["lat"] = frame["lat"].astype(float)
    logger.info("窗口 %s ~ %s: %d 行 / %d 个观测点", start, end, len(frame), frame["uid"].nunique())
    return frame[["uid", "lat", MONTH_COL, MERGED_VALUE_COL, SOURCE_COL, ATT_COL, POWER_COL]]


def check_month_coverage(frame: pd.DataFrame, logger) -> None:
    """核对逐月站点数与时间轴连续性：某月缺点会拉低该月可比性，必须显式暴露。"""
    per_month = frame.groupby(MONTH_COL)["uid"].nunique()
    expected = int(frame["uid"].nunique())
    logger.info("逐月站点数: 满覆盖(%d 点) %d 个月 / 共 %d 个月",
                expected, int((per_month == expected).sum()), len(per_month))

    short = per_month[per_month < expected]
    if short.empty:
        logger.info("各月站点数一致，序列可比，无需站点数校正")
    else:
        logger.warning("%d 个月未满覆盖，最少 %d 点，例如: %s", len(short), int(short.min()),
                       ", ".join(f"{m}({n})" for m, n in short.head(5).items()))

    full_range = pd.period_range(per_month.index.min(), per_month.index.max(), freq="M")
    gaps = full_range.difference(per_month.index)
    if len(gaps):
        logger.warning("时间轴缺 %d 个月，例如: %s", len(gaps), ", ".join(str(m) for m in gaps[:5]))
    else:
        logger.info("时间轴连续，无缺月")


# --------------------------------------------------------------------------- #
# 取值策略：决定每行取哪一列，以及是否抬平跨源台阶
# --------------------------------------------------------------------------- #
def estimate_power_bias(frame: pd.DataFrame, correction: str, logger):
    """估计 POWER 相对附件的系统性偏低量（重叠期 att − power），返回 None/常数/逐城市 Series。"""
    if correction not in BIAS_MODES:
        raise ValueError(f"未知的 power_bias_correction: {correction}（可选 {BIAS_MODES}）")
    if correction == "none":
        logger.info("POWER 偏差修正: 关闭（跨源台阶保留）")
        return None

    overlap = frame.dropna(subset=[ATT_COL, POWER_COL])
    if overlap.empty:
        raise ValueError("没有重叠月份，无法估计 POWER 偏差，请把修正模式改回 none")

    diff = overlap[ATT_COL] - overlap[POWER_COL]
    if correction == "global":
        bias = float(diff.mean())
        logger.info("POWER 偏差修正: 全局常数 %+.3f ℃（重叠 %d 行）", bias, len(overlap))
        return bias

    per_city = diff.groupby(overlap["uid"]).mean()
    logger.info("POWER 偏差修正: 逐城市，中位 %+.3f ℃ / 范围 %+.3f ~ %+.3f / %d 个城市有重叠",
                per_city.median(), per_city.min(), per_city.max(), len(per_city))
    return per_city


def bias_offset(uid: pd.Series, bias, from_power: pd.Series) -> pd.Series:
    """把偏差铺成逐行偏移量：只有取自 POWER 的行抬升，其他行偏移为 0。"""
    if isinstance(bias, pd.Series):
        mapped = bias.reindex(uid).fillna(bias.mean())   # 无重叠的城市退回全局均值
        offset = pd.Series(mapped.to_numpy(), index=uid.index)
    else:
        offset = pd.Series(float(bias), index=uid.index)
    return offset.where(from_power, 0.0)


def select_values(frame: pd.DataFrame, mode: str, bias, logger) -> pd.DataFrame:
    """按策略生成聚合用的 value 列，剔除该策略下无值的行，并报告实际时段与 POWER 占比。"""
    if mode not in VALUE_MODES:
        raise ValueError(f"未知的取值策略: {mode}（可选 {VALUE_MODES}）")

    out = frame.copy()
    if mode == "tmean":
        out[VALUE_COL] = out[MERGED_VALUE_COL]
        from_power = out[SOURCE_COL].isin(POWER_SOURCES)
    elif mode == "att":
        out[VALUE_COL] = out[ATT_COL]
        from_power = pd.Series(False, index=out.index)
    else:
        out[VALUE_COL] = out[POWER_COL]
        from_power = pd.Series(True, index=out.index)

    if bias is not None:
        out[VALUE_COL] = out[VALUE_COL] + bias_offset(out["uid"], bias, from_power)

    n_missing = int(out[VALUE_COL].isna().sum())
    if n_missing:
        logger.warning("取值策略 %s 下有 %d 行无值，按缺失剔除", mode, n_missing)
        out, from_power = out.dropna(subset=[VALUE_COL]), from_power[out[VALUE_COL].notna()]
    if out.empty:
        raise ValueError(f"取值策略 {mode} 下窗口内无可用数据")

    power_share = 100.0 * float(from_power.mean())
    logger.info("取值策略 %s: 保留 %d 行，其中取自 POWER 的占 %.1f%%，实际时段 %s ~ %s",
                mode, len(out), power_share, out[MONTH_COL].min(), out[MONTH_COL].max())
    return out[["uid", "lat", MONTH_COL, VALUE_COL]]


# --------------------------------------------------------------------------- #
# 权重与聚合
# --------------------------------------------------------------------------- #
def add_weight_columns(frame: pd.DataFrame, weights_cfg: dict,
                       logger) -> tuple[pd.DataFrame, list[str]]:
    """按配置挂权重列（等权恒为 1；面积权重取 cos 纬度），返回 (表, 启用口径列表)。"""
    enabled = [key for key in WEIGHT_SPECS if weights_cfg.get(key, False)]
    if not enabled:
        raise ValueError("global.weights 至少要开一种口径（equal / coslat）")

    out = frame.copy()
    for key in enabled:
        spec = WEIGHT_SPECS[key]
        out[spec["weight"]] = 1.0 if key == "equal" else np.cos(np.deg2rad(out["lat"]))
        logger.info("启用口径 %-6s -> %-12s 权重 %.3f ~ %.3f（%s）", key, spec["output"],
                    out[spec["weight"]].min(), out[spec["weight"]].max(), spec["label"])
    if disabled := sorted(set(WEIGHT_SPECS) - set(enabled)):
        logger.info("未启用的口径: %s", ", ".join(disabled))
    return out, enabled


def monthly_weighted_mean(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """逐月加权平均 Σ(w·t)/Σ(w)，并记录参与平均的站点数。

    注意：work 是全新 RangeIndex，故各列统一用 to_numpy() 传入，
    不能直接塞带原索引的 Series（会按标签对齐成 NaN）。
    """
    values = frame[VALUE_COL].to_numpy(dtype=float)
    work = pd.DataFrame({MONTH_COL: frame[MONTH_COL].to_numpy()})
    for key in keys:
        weight = frame[WEIGHT_SPECS[key]["weight"]].to_numpy(dtype=float)
        work[f"_num_{key}"] = weight * values
        work[f"_den_{key}"] = weight

    sums = work.groupby(MONTH_COL).sum()
    out = pd.DataFrame(index=sums.index)
    out[COUNT_COL] = frame.groupby(MONTH_COL)["uid"].nunique()
    for key in keys:
        out[WEIGHT_SPECS[key]["output"]] = sums[f"_num_{key}"] / sums[f"_den_{key}"]
    return out


def finalize_table(monthly: pd.DataFrame, keys: list[str], decimals: int) -> pd.DataFrame:
    """整理落盘格式：date + 站点数 + 各口径月均值，按日期升序。"""
    out = monthly.copy()
    out[DATE_COL] = out.index.to_timestamp()
    columns = [DATE_COL, COUNT_COL] + [WEIGHT_SPECS[key]["output"] for key in keys]
    out = out[columns].sort_values(DATE_COL).reset_index(drop=True)
    for key in keys:
        column = WEIGHT_SPECS[key]["output"]
        out[column] = out[column].round(decimals)
    return out


# --------------------------------------------------------------------------- #
# 结果核对
# --------------------------------------------------------------------------- #
def decadal_trend(values: pd.Series, months: pd.DatetimeIndex) -> float:
    """一次线性拟合斜率换算成 ℃/10a，用于日志核对趋势方向与量级。"""
    years = months.year + (months.month - 1) / 12.0
    slope = np.polyfit(years.astype(float), values.to_numpy(dtype=float), 1)[0]
    return float(slope * 10)


def summarize(table: pd.DataFrame, keys: list[str], logger) -> None:
    """日志核对：各口径的首末月、均值、长期趋势；两口径时再报差值与相关。"""
    months = pd.DatetimeIndex(table[DATE_COL])
    for key in keys:
        column = WEIGHT_SPECS[key]["output"]
        series = table[column]
        logger.info("%-13s 首月 %.2f ℃ | 末月 %.2f ℃ | 均值 %.2f ℃ | 趋势 %+.2f ℃/10a",
                    column, series.iloc[0], series.iloc[-1], series.mean(),
                    decadal_trend(series, months))

    if len(keys) == 2:
        first, second = (WEIGHT_SPECS[key]["output"] for key in keys)
        diff = table[second] - table[first]
        logger.info("两口径差 (%s - %s): 均值 %+.3f ℃ | 绝对均值 %.3f ℃ | 最大 %.3f ℃ | 相关 %.4f",
                    second, first, diff.mean(), diff.abs().mean(), diff.abs().max(),
                    table[first].corr(table[second]))


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def run(cfg: dict, logger) -> pd.DataFrame:
    """读入 -> 取值策略 -> 校验 -> 加权 -> 逐月聚合 -> 核对 -> 落盘。"""
    global_cfg = cfg["global"]
    policy = global_cfg["value_policy"]
    mode, correction = policy["mode"], policy["power_bias_correction"]
    logger.info("取值策略: mode=%s | POWER 修正=%s", mode, correction)

    frame = load_merged(cfg, logger)
    bias = estimate_power_bias(frame, correction, logger)
    frame = select_values(frame, mode, bias, logger)
    check_month_coverage(frame, logger)

    weighted, keys = add_weight_columns(frame, global_cfg["weights"], logger)
    monthly = monthly_weighted_mean(weighted, keys)
    table = finalize_table(monthly, keys, int(global_cfg.get("decimals", 3)))

    logger.info("聚合完成: %d 个月（%s ~ %s）", len(table),
                table[DATE_COL].iloc[0].strftime("%Y-%m"), table[DATE_COL].iloc[-1].strftime("%Y-%m"))
    summarize(table, keys, logger)

    target = Path(cfg["paths"]["result_dir"]) / global_cfg["output_file"]
    save_csv(table, target, logger)
    return table


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q1 stage_1：按月计算全球平均气温")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="配置文件路径")
    parser.add_argument("--mode", choices=VALUE_MODES, help="临时覆盖取值策略（不改配置文件）")
    parser.add_argument("--power-bias", choices=BIAS_MODES, dest="power_bias",
                        help="临时覆盖 POWER 偏差修正模式")
    return parser.parse_args(argv)


def load_config(config_path, args=None) -> dict:
    """读取本阶段配置，校验必需段落，并允许命令行临时覆盖取值策略。"""
    raw = load_json(config_path)
    for key in ("paths", "global"):
        if key not in raw:
            raise KeyError(f"配置缺少必需字段: {key}")

    cfg = {"paths": raw["paths"], "global": raw["global"]}
    policy = cfg["global"].setdefault("value_policy",
                                      {"mode": "tmean", "power_bias_correction": "none"})
    if args is not None and args.mode:
        policy["mode"] = args.mode
    if args is not None and args.power_bias:
        policy["power_bias_correction"] = args.power_bias
    return cfg


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, args)
    logger = setup_logger(Path(cfg["paths"]["log_dir"]) / LOG_NAME, "q1_stage1_global")
    logger.info("配置: %s", resolve_path(args.config))
    try:
        run(cfg, logger)
    except Exception:
        logger.exception("stage_1 全球月均温聚合异常终止")
        return 1
    logger.info("全部完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
