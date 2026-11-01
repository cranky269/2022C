
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_squared_error, mean_absolute_error
from itertools import product

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. 基本参数
# ============================================================

DATA_PATH = "temperature.csv"

DATE_COL = "Date"
TEMP_COL = "Temperature_Celsius"

# 数据截止时间
DATA_END = "2022-12-01"

# 预测截止时间：2022年3月之前，即2022年2月
FORECAST_END = "2500-12-01"

# 月度数据：12个月为一个周期
SEASONAL_PERIOD = 12

# 历史验证集：2003年1月 - 2012年12月
VALIDATION_START = "2013-01-01"


# ============================================================
# 2. 读取和预处理数据
# ============================================================

df = pd.read_csv(DATA_PATH)

df[DATE_COL] = pd.to_datetime(df[DATE_COL])

df = df.sort_values(DATE_COL)
df = df.set_index(DATE_COL)

# 转换为月度时间序列
df = df[[TEMP_COL]].copy()

df[TEMP_COL] = pd.to_numeric(
    df[TEMP_COL], errors="coerce"
)

# 统一到每月月初
df.index = df.index.to_period("M").to_timestamp()

# 检查重复月份
if df.index.duplicated().any():
    raise ValueError("数据中存在重复月份，请先处理。")

# 建立完整月度索引
full_index = pd.date_range(
    start=df.index.min(),
    end=df.index.max(),
    freq="MS"
)

df = df.reindex(full_index)

# 缺失值检查
missing_count = df[TEMP_COL].isna().sum()

print("数据总量：", len(df))
print("缺失值数量：", missing_count)

# 采用时间插值处理少量缺失值
# 如果缺失比例较高，应先分析缺失机制
if missing_count > 0:
    df[TEMP_COL] = df[TEMP_COL].interpolate(
        method="time",
        limit_area="inside"
    )

if df[TEMP_COL].isna().any():
    raise ValueError(
        "序列仍有缺失值，请检查首尾缺失数据。"
    )

# 截取历史数据
df = df.loc[:DATA_END]

y = df[TEMP_COL].astype(float)

print("\n数据时间范围：")
print(y.index.min(), "至", y.index.max())


# ============================================================
# 6. 划分训练集和验证集
# ============================================================

train = y.loc[: "2012-12-01"]

valid = y.loc["2013-01-01":"2022-12-01"]

print("\n训练集范围：")
print(train.index.min(), "至", train.index.max())

print("\n验证集范围：")
print(valid.index.min(), "至", valid.index.max())

print("训练集样本数：", len(train))
print("验证集样本数：", len(valid))

# ============================================================
# 9. 使用完整历史数据重新训练
# ============================================================

final_model = SARIMAX(
    y,
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 12),
    trend='c',
    enforce_stationarity=False,
    enforce_invertibility=False
)

final_result = final_model.fit(
    disp=False,
    maxiter=300
)

print("\n最终模型摘要：")
print(final_result.summary())


# ============================================================
# 10. 预测2023年1月—2100年12月
# ============================================================

future_index = pd.date_range(
    start="2023-01-01",
    end="2500-12-01",
    freq="MS"
)

forecast_result = final_result.get_forecast(
    steps=len(future_index)
)

forecast_mean = forecast_result.predicted_mean
forecast_ci = forecast_result.conf_int()

forecast_mean.index = future_index
forecast_ci.index = future_index

forecast_df = pd.DataFrame({
    "date": future_index,
    "predicted_temperature": forecast_mean.values,
    "lower_95": forecast_ci.iloc[:, 0].values,
    "upper_95": forecast_ci.iloc[:, 1].values
})

forecast_df.to_csv(
    "temperature_forecast_2023_2100.csv",
    index=False
)

print("预测月份数量：", len(forecast_df))

# ============================================================
# 1. 提取 2022—2500 年的 SARIMA 月度预测温度
# ============================================================

# 确保索引为 DatetimeIndex
forecast_mean.index = pd.to_datetime(forecast_mean.index)

# 提取 2022—2500 年的预测数据
forecast_data = forecast_mean.loc[
    (forecast_mean.index >= "2022-01-01") &
    (forecast_mean.index < "3001-01-01")
]

# ============================================================
# 2. 计算每年的12个月平均气温
# ============================================================

# 按自然年计算平均值
annual_mean = forecast_data.resample("YE").mean()

# 统计每年实际包含的预测月份数量
annual_count = forecast_data.resample("YE").count()

# 只保留具有完整12个月预测数据的年份
annual_mean = annual_mean[annual_count == 12]

# 将横坐标设置为每年的 6 月 1 日
annual_mean.index = pd.to_datetime(
    annual_mean.index.year.astype(str) + "-06-01"
)

# 限制年份范围
annual_mean = annual_mean.loc[
    (annual_mean.index.year >= 2022) &
    (annual_mean.index.year <= 2500)
]

# ============================================================
# 3. 寻找年度平均气温首次超过20°C的年份
# ============================================================

threshold = 20

exceed_years = annual_mean[annual_mean > threshold]

if len(exceed_years) > 0:

    # 首次超过20°C的年份
    exceed_date = exceed_years.index[0]
    exceed_year = exceed_date.year
    exceed_temperature = exceed_years.iloc[0]

    print(f"首次超过20°C的年份：{exceed_year}")
    print(f"该年年度平均气温：{exceed_temperature:.4f} °C")

else:
    exceed_year = None

    print("截至2500年，年度平均气温尚未超过20°C。")

# ============================================================
# 4. 绘制2022—2500年年度平均气温曲线
# ============================================================

plt.figure(figsize=(15, 6))

# SARIMA年度平均气温曲线
plt.plot(
    annual_mean.index,
    annual_mean.values,
    linewidth=2,
    linestyle="-",
    marker="o",
    markersize=3,
    label="SARIMA Annual Mean Temperature"
)

# 20°C水平参考线
plt.axhline(
    y=threshold,
    color="red",
    linestyle="--",
    linewidth=1.5,
    label="20°C Threshold"
)

# ============================================================
# 5. 绘制首次超过20°C年份的竖直分界线
# ============================================================

if exceed_year is not None:

    exceed_x = pd.Timestamp(f"{exceed_year}-06-01")

    plt.axvline(
        x=exceed_x,
        color="red",
        linestyle=":",
        linewidth=2,
        label=f"First Exceedance: {exceed_year}"
    )

    # 标记首次超过20°C的点
    plt.scatter(
        exceed_x,
        exceed_temperature,
        color="red",
        s=70,
        zorder=5
    )

    # 标注年份
    plt.annotate(
        f"{exceed_year}\n{exceed_temperature:.2f} °C",
        xy=(exceed_x, exceed_temperature),
        xytext=(12, 15),
        textcoords="offset points",
        fontsize=10,
        color="red",
        arrowprops=dict(
            arrowstyle="->",
            color="red"
        )
    )

# ============================================================
# 6. 图像设置
# ============================================================

plt.xlabel("Year", fontsize=12)
plt.ylabel("Annual Mean Temperature (°C)", fontsize=12)

plt.title(
    "SARIMA Predicted Annual Mean Temperature (2022–2500)",
    fontsize=14
)

plt.xlim(
    pd.Timestamp("2022-01-01"),
    pd.Timestamp("2500-12-31")
)

plt.grid(alpha=0.3)
plt.legend(fontsize=10)

plt.tight_layout()

plt.savefig(
    "SARIMA_Annual_Temperature_2022_2500.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()
