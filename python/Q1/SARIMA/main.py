
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


# ============================================================
# 1. 基本参数
# ============================================================

DATA_PATH = "temperature.csv"

DATE_COL = "Date"
TEMP_COL = "Temperature_Celsius"

# 数据截止时间
DATA_END = "2022-12-01"

# 预测截止时间：2022年3月之前，即2022年2月
FORECAST_END = "2100-12-01"

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
# 3. 原始数据可视化
# ============================================================

plt.figure(figsize=(14, 5))

plt.plot(y.index, y.values, linewidth=0.8)

plt.title("Global Average Temperature (1800-2012)")
plt.xlabel("Year")
plt.ylabel("Temperature (°C)")

plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("01_original_temperature.png", dpi=300)
plt.show()


# # ============================================================
# # 4. ADF平稳性检验
# # ============================================================

# def adf_test(series, name):
#     result = adfuller(series.dropna(), autolag="AIC")

#     print(f"\n{name} ADF检验")
#     print("-" * 40)
#     print("ADF Statistic:", result[0])
#     print("p-value:", result[1])
#     print("Used lags:", result[2])

#     if result[1] < 0.05:
#         print("结论：拒绝单位根原假设，序列可以认为平稳。")
#     else:
#         print("结论：不能拒绝单位根原假设，序列可能非平稳。")


# adf_test(y, "原始序列")

# # 一阶普通差分
# y_diff1 = y.diff().dropna()
# adf_test(y_diff1, "一阶差分序列")

# # 二阶普通差分
# y_diff2 = y.diff().diff().dropna()
# adf_test(y_diff2, "二阶差分序列")

# # 一阶季节差分
# y_seasonal_diff = y.diff(SEASONAL_PERIOD).dropna()
# adf_test(y_seasonal_diff, "一阶季节差分序列")


# # ============================================================
# # 5. ACF和PACF分析
# # ============================================================

# # 原始序列的ACF/PACF
# fig, axes = plt.subplots(2, 1, figsize=(12, 7))

# plot_acf(y, lags=48, ax=axes[0])
# axes[0].set_title("ACF - Original Series")

# plot_pacf(y, lags=48, ax=axes[1], method="ywm")
# axes[1].set_title("PACF - Original Series")

# plt.tight_layout()
# plt.savefig("02_original_acf_pacf.png", dpi=300)
# plt.show()


# # 一阶差分序列的ACF/PACF
# fig, axes = plt.subplots(2, 1, figsize=(12, 7))

# plot_acf(y_diff1, lags=48, ax=axes[0])
# axes[0].set_title("ACF - First Difference")

# plot_pacf(y_diff1, lags=48, ax=axes[1], method="ywm")
# axes[1].set_title("PACF - First Difference")

# plt.tight_layout()
# plt.savefig("03_diff_acf_pacf.png", dpi=300)
# plt.show()


# # ============================================================
# # 6. 划分训练集和验证集
# # ============================================================

# train = y.loc[: "2012-12-01"]

# valid = y.loc["2013-01-01":"2022-12-01"]

# print("\n训练集范围：")
# print(train.index.min(), "至", train.index.max())

# print("\n验证集范围：")
# print(valid.index.min(), "至", valid.index.max())

# print("训练集样本数：", len(train))
# print("验证集样本数：", len(valid))


# # ============================================================
# # 7. SARIMA参数搜索
# # ============================================================

# # 普通AR阶数
# p_values = [0, 1, 2]

# # 普通差分阶数
# d_values = [0, 1, 2]

# # 普通MA阶数
# q_values = [0, 1, 2]

# # 季节性AR阶数
# P_values = [0, 1]

# # 季节性差分阶数
# D_values = [0, 1]

# # 季节性MA阶数
# Q_values = [0, 1]


# candidates = []

# print("\n开始搜索SARIMA模型参数...")

# for p, d, q, P, D, Q in product(
#     p_values,
#     d_values,
#     q_values,
#     P_values,
#     D_values,
#     Q_values
# ):

#     order = (p, d, q)

#     seasonal_order = (
#         P, D, Q, SEASONAL_PERIOD
#     )

#     # 对差分模型允许线性趋势（漂移项）
#     # 对未差分模型使用常数项
#     trend = "t" if (d + D) > 0 else "c"

#     try:
#         model = SARIMAX(
#             train,
#             order=order,
#             seasonal_order=seasonal_order,
#             trend=trend,
#             enforce_stationarity=False,
#             enforce_invertibility=False
#         )

#         result = model.fit(
#             disp=False,
#             maxiter=200
#         )

#         candidates.append({
#             "order": order,
#             "seasonal_order": seasonal_order,
#             "trend": trend,
#             "aic": result.aic,
#             "bic": result.bic
#         })

#     except Exception:
#         continue


# if len(candidates) == 0:
#     raise RuntimeError("没有成功拟合的SARIMA模型。")

# # 按照AIC从小到大排序
# candidate_df = pd.DataFrame(candidates)

# candidate_df = candidate_df.sort_values("aic")

# print("\nAIC排名前10的模型：")

# print(candidate_df.head(10).to_string(index=False))

# candidate_df.to_csv(
#     "sarima_candidates.csv",
#     index=False
# )


# # ============================================================
# # 8. 使用验证集筛选最优模型
# # ============================================================

# # 从AIC排名靠前的模型中选择
# top_candidates = candidate_df.head(10)

# validation_results = []

# for _, row in top_candidates.iterrows():

#     order = row["order"]
#     seasonal_order = row["seasonal_order"]
#     trend = row["trend"]

#     try:
#         model = SARIMAX(
#             train,
#             order=order,
#             seasonal_order=seasonal_order,
#             trend=trend,
#             enforce_stationarity=False,
#             enforce_invertibility=False
#         )

#         result = model.fit(
#             disp=False,
#             maxiter=200
#         )

#         # 预测验证集
#         prediction = result.get_forecast(
#             steps=len(valid)
#         ).predicted_mean

#         # 对齐时间索引
#         prediction.index = valid.index

#         rmse = np.sqrt(
#             mean_squared_error(valid, prediction)
#         )

#         mae = mean_absolute_error(
#             valid, prediction
#         )

#         validation_results.append({
#             "order": order,
#             "seasonal_order": seasonal_order,
#             "trend": trend,
#             "AIC": result.aic,
#             "BIC": result.bic,
#             "RMSE": rmse,
#             "MAE": mae
#         })

#     except Exception as e:
#         print("模型验证失败：", order, seasonal_order, e)


# if len(validation_results) == 0:
#     raise RuntimeError("所有候选模型验证均失败。")

# validation_df = pd.DataFrame(validation_results)

# validation_df = validation_df.sort_values("RMSE")

# print("\n验证集模型性能排名：")

# print(validation_df.to_string(index=False))

# validation_df.to_csv(
#     "sarima_validation_results.csv",
#     index=False
# )

# # 选择验证集RMSE最低的模型
# best = validation_df.iloc[0]

# best_order = best["order"]
# best_seasonal_order = best["seasonal_order"]
# best_trend = best["trend"]

# print("\n最优SARIMA模型：")
# print("order =", best_order)
# print("seasonal_order =", best_seasonal_order)
# print("trend =", best_trend)
# print("Validation RMSE =", best["RMSE"])
# print("Validation MAE =", best["MAE"])


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
    end="2100-12-01",
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
# 11. 绘制最终预测结果
# ============================================================

plt.figure(figsize=(15, 6))

# ------------------------------------------------------------
# 1. 计算并绘制每年的平均气温（历史 + 预测）
# ------------------------------------------------------------

# 合并历史数据和预测数据
all_temperature = pd.concat([y, forecast_mean])

# 确保索引是 DatetimeIndex
all_temperature.index = pd.to_datetime(all_temperature.index)

# 按自然年计算平均气温
annual_mean = all_temperature.resample("YE").mean()

# 将横坐标设置为每年的 06-01
annual_index = pd.to_datetime(
    annual_mean.index.year.astype(str) + "-06-01"
)

# 绘制年度平均气温
plt.plot(
    annual_index,
    annual_mean.values,
    label="Annual Mean Temperature",
    linewidth=2,
    linestyle="-.",
    marker="o",
    markersize=1
)

# 历史数据
plt.plot(
    y.index,
    y.values,
    label="Historical Temperature",
    linewidth=1
)

# 预测数据
plt.plot(
    future_index,
    forecast_mean.values,
    label="SARIMA Forecast",
    linewidth=1.5
)


plt.axvline(
    x=y.index[-1],
    linestyle="--",
    alpha=0.7,
    label="Forecast Start"
)

plt.title("SARIMA Global Temperature Forecast")
plt.xlabel("Year")
plt.ylabel("Temperature (°C)")

plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()

plt.savefig(
    "04_sarima_forecast.png",
    dpi=300
)

plt.show()


# ============================================================
# 13. 保存最终模型参数
# ============================================================

print("\n========== 最终结果 ==========")

print("最优模型：")
print(
    f"SARIMA{(1, 1, 1)}{(1, 1, 1, 12)}"
)

print("预测起始时间：", future_index[0])
print("预测结束时间：", future_index[-1])

print("\n所有文件已保存。")
