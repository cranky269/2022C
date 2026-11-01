# -*- coding: utf-8 -*-
"""Q1 数据缺失值检查脚本
输出：控制台摘要 + result/Q1/missing_*.csv 表
"""
import os
import re
import numpy as np
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(BASE, "data", "2022_APMCM_C_Data.csv")
OUT = os.path.join(BASE, "result", "Q1")
os.makedirs(OUT, exist_ok=True)

# ---------- 1. 原始结构检查 ----------
raw = open(DATA, "rb").read()
enc = None
for cand in ("utf-8-sig", "gb18030"):
    try:
        text = raw.decode(cand)
        enc = cand
        break
    except UnicodeDecodeError:
        continue
if enc is None:
    text = raw.decode("latin-1")
    enc = "latin-1"
lines = text.splitlines()
print(f"[结构] 文件字节数={len(raw):,}  编码={enc}")
print(f"[结构] 总行数={len(lines):,}  空行={sum(1 for l in lines if not l.strip())}")
print(f"[结构] 表头={lines[0]}")

fmt = [("YYYY-MM-DD", r"^\d{4}-\d{2}-\d{2},"), ("YYYY/M/D", r"^\d{4}/\d{1,2}/\d{1,2},")]
body = [l for l in lines[1:] if l.strip()]
for name, pat in fmt:
    print(f"[结构] dt 格式 {name}: {sum(1 for l in body if re.match(pat, l)):,}")
other = [l for l in body if not any(re.match(p, l) for _, p in fmt)]
print(f"[结构] 其他格式行数: {len(other)}")

# ---------- 2. 读入 ----------
df = pd.read_csv(DATA, encoding=enc, dtype=str, keep_default_na=False)
print(f"\n[形状] 记录数={len(df):,}  列数={df.shape[1]}")

# 统一日期
df["dt"] = df["dt"].str.strip().str.replace("/", "-", regex=False)
dt = pd.to_datetime(df["dt"], format="mixed", errors="coerce")
print(f"[日期] 无法解析的 dt 数量={dt.isna().sum()}")
df["dt"] = dt                      # 统一为 datetime，避免非补零日期串比较出错
df["year"] = dt.dt.year
df["month"] = dt.dt.month

# 缺失判定：空字符串 / 纯空白 / 常见占位符
NA_TOKENS = {"", "na", "nan", "n/a", "null", "none", "-", "?", "--"}
def missing_mask(s):
    return s.astype(str).str.strip().str.lower().isin(NA_TOKENS)

print("\n[缺失] 各列缺失统计")
rows = []
for c in df.columns:
    if c in ("year", "month"):
        continue
    m = missing_mask(df[c])
    rows.append({"列名": c, "缺失数": int(m.sum()), "缺失率(%)": round(m.mean() * 100, 4)})
tbl_col = pd.DataFrame(rows)
print(tbl_col.to_string(index=False))

# ---------- 3. 缺失共现 ----------
mt = missing_mask(df["AverageTemperature"])
mu = missing_mask(df["AverageTemperatureUncertainty"])
print(f"\n[共现] 温度与不确定度同时缺失={(mt & mu).sum():,}")
print(f"[共现] 仅温度缺失={(mt & ~mu).sum():,}  仅不确定度缺失={(~mt & mu).sum():,}")

# ---------- 4. 数值型异常（非缺失）----------
temp = pd.to_numeric(df["AverageTemperature"].where(~mt), errors="coerce")
unc = pd.to_numeric(df["AverageTemperatureUncertainty"].where(~mu), errors="coerce")
print(f"[数值] 温度非缺失但无法转数值={int((temp.isna() & ~mt).sum())}")
print(f"[数值] 温度范围=[{temp.min():.3f}, {temp.max():.3f}]  均值={temp.mean():.3f}")
print(f"[数值] 不确定度范围=[{unc.min():.3f}, {unc.max():.3f}]  均值={unc.mean():.3f}")

# 坐标列格式
def parse_coord(s, hemi):
    s = s.str.strip().str.upper()
    ok = s.str.match(rf"^\d+(\.\d+)?[{hemi}]$")
    val = pd.to_numeric(s.str[:-1], errors="coerce")
    return ok, val, s.str[-1]

lat_ok, lat_v, lat_h = parse_coord(df["Latitude"], "NS")
lon_ok, lon_v, lon_h = parse_coord(df["Longitude"], "EW")
print(f"[坐标] Latitude 格式异常={int((~lat_ok).sum())}  Longitude 格式异常={int((~lon_ok).sum())}")
print(f"[坐标] 纬度范围=[{lat_v.min():.2f}, {lat_v.max():.2f}] 经度范围=[{lon_v.min():.2f}, {lon_v.max():.2f}]")

# ---------- 5. 重复与覆盖度 ----------
df["cid"] = df["City"].str.strip() + " | " + df["Country"].str.strip()
dup = df.duplicated(["dt", "cid"]).sum()
print(f"\n[键] 城市数={df['City'].nunique()}  国家数={df['Country'].nunique()}  城市-国家组合={df['cid'].nunique()}")
print(f"[键] dt+城市 重复记录数={dup}")
print(f"[时间] 起={dt.min().date()}  止={dt.max().date()}  月份跨度={(dt.max().year - dt.min().year) * 12 + dt.max().month - dt.min().month + 1}")

# 隐含缺失（整月整行缺失）：完整网格 - 实际行数
span_all = (dt.max().year - dt.min().year) * 12 + dt.max().month - dt.min().month + 1
full_grid = span_all * df["cid"].nunique()
cov = df.groupby("cid")["dt"].agg(n="size", first="min", last="max")
cov["first"] = pd.to_datetime(cov["first"])
cov["last"] = pd.to_datetime(cov["last"])
cov["span"] = ((cov["last"].dt.year - cov["first"].dt.year) * 12
               + (cov["last"].dt.month - cov["first"].dt.month) + 1)
print(f"[覆盖] 全量完整网格={full_grid:,}  实际记录={len(df):,}  隐含缺失={full_grid - len(df):,} "
      f"({(full_grid - len(df)) / full_grid * 100:.2f}%)")
print(f"[覆盖] 存在整月缺行的城市数={(cov['span'] != cov['n']).sum()}")
print(f"[覆盖] 城市起始年份种类={cov['first'].dt.year.nunique()}  结束年份={sorted(cov['last'].dt.year.unique())}")

# 完全无缺失的连续区块
sub = df[(df["dt"] >= "1900-01-01") & (df["dt"] <= "2013-08-01")]
print(f"[区块] 1900-01~2013-08 记录数={len(sub):,}  缺失={int(missing_mask(sub['AverageTemperature']).sum())}  "
      f"城市数={sub['cid'].nunique()}")

# ---------- 6. 按年份 / 城市 / 月份 ----------
by_year = (df.assign(miss=mt).groupby("year")
           .agg(记录数=("dt", "size"), 缺失数=("miss", "sum")))
by_year["缺失率(%)"] = (by_year["缺失数"] / by_year["记录数"] * 100).round(3)
by_year.to_csv(os.path.join(OUT, "missing_by_year.csv"), encoding="utf-8-sig")

by_city = (df.assign(miss=mt).groupby("cid")
           .agg(记录数=("dt", "size"), 缺失数=("miss", "sum")))
by_city["缺失率(%)"] = (by_city["缺失数"] / by_city["记录数"] * 100).round(2)
by_city = by_city.sort_values(["缺失率(%)", "缺失数"], ascending=False)
by_city.to_csv(os.path.join(OUT, "missing_by_city.csv"), encoding="utf-8-sig")

# 城市级明细：起止时间与记录时长
detail = cov.join(by_city[["缺失数", "缺失率(%)"]]).rename(
    columns={"n": "记录数", "first": "起始月份", "last": "结束月份", "span": "时间跨度(月)"})
detail = detail.sort_values("缺失率(%)", ascending=False)
detail.to_csv(os.path.join(OUT, "missing_by_city_detail.csv"), encoding="utf-8-sig")
print(f"\n[城市] 存在缺失的城市数={(by_city['缺失数'] > 0).sum()} / {len(by_city)}")
print("[城市] 缺失最严重 Top15")
print(by_city.head(15).to_string())

by_month = df.assign(miss=mt).groupby("month").agg(记录数=("dt", "size"), 缺失数=("miss", "sum"))
by_month["缺失率(%)"] = (by_month["缺失数"] / by_month["记录数"] * 100).round(3)
print("\n[月份]")
print(by_month.rename(columns={"记录数": "记录数", "缺失数": "缺失数"})[["缺失数", "缺失率(%)"]].to_string())

# ---------- 7. 连续缺失游程 ----------
gaps = []
for cid, g in df.assign(miss=mt).sort_values("dt").groupby("cid", sort=False):
    m = g["miss"].to_numpy()
    if not m.any():
        continue
    idx = np.flatnonzero(m)
    start = idx[0]
    prev = idx[0]
    for i in idx[1:]:
        if i != prev + 1:
            gaps.append((cid, start, prev))
            start = i
        prev = i
    gaps.append((cid, start, prev))
gap_df = pd.DataFrame(gaps, columns=["城市", "起始行", "结束行"])
gap_df["连续缺失月数"] = gap_df["结束行"] - gap_df["起始行"] + 1
# 行号映射到日期
dates = df["dt"].dt.strftime("%Y-%m").to_numpy()
gap_df["起始月份"] = [dates[int(i)] for i in gap_df["起始行"]]
gap_df["结束月份"] = [dates[int(i)] for i in gap_df["结束行"]]
gap_df = gap_df.drop(columns=["起始行", "结束行"]).sort_values("连续缺失月数", ascending=False)
gap_df.to_csv(os.path.join(OUT, "missing_gaps.csv"), index=False, encoding="utf-8-sig")
print(f"\n[游程] 连续缺失片段总数={len(gap_df)}")
print(f"[游程] 最长连续缺失={gap_df['连续缺失月数'].max()} 个月")
print("[游程] 最长片段 Top10")
print(gap_df.head(10).to_string(index=False))
print("\n[游程] 长度分布")
print(gap_df["连续缺失月数"].value_counts().sort_index().head(20).to_string())

# ---------- 8. 缺失随时间(年代) ----------
df["decade"] = (df["year"] // 10) * 10
by_dec = df.assign(miss=mt).groupby("decade").agg(记录数=("dt", "size"), 缺失数=("miss", "sum"))
by_dec["缺失率(%)"] = (by_dec["缺失数"] / by_dec["记录数"] * 100).round(2)
print("\n[年代]")
print(by_dec.to_string())
by_dec.to_csv(os.path.join(OUT, "missing_by_decade.csv"), encoding="utf-8-sig")

print(f"\n[输出] 明细表已写入 {OUT}")
