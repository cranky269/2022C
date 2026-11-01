# Q1 文件架构说明

> 记录 Q1 各目录下每个文件的含义与作用，方便后期查看。

## 根目录（项目级，Q1 相关）

| 文件/目录 | 作用 |
|---|---|
| `config_pic.json` | 全项目统一绘图配置（配色/字体/尺寸），所有画图脚本从这里取样式，不硬编码颜色 |
| `requirements.txt` | Python 依赖清单（含库名与版本注释），Q1 使用 pandas / numpy / matplotlib / openpyxl |

## python/Q1（程序文件）

| 文件/目录 | 作用 |
|---|---|
| `check_missing.py` | Q1 数据缺失值检查脚本（早期数据探查，输出缺失统计到 result/Q1） |
| `common/pic_config.py` | Q1 通用函数：加载根目录 `config_pic.json` 并应用到 matplotlib（字体/字号/配色） |
| `stage_1/plot_temperature_trends.py` | 阶段1：气温趋势与年代增幅可视化。绘制 3 月气温趋势图、年均气温趋势图，以及两者的年代增幅图（相邻十年均值之差 + 每十年内部首尾差），并把年代统计表导出 xlsx |
| `docs/file_tree.md` | 本文件：Q1 文件架构说明 |

## image/Q1（输出图片）

| 文件 | 作用 |
|---|---|
| `march_temperature_trend.png` | 图1：全球历年 3 月平均气温趋势（年值 + 10 年滑动平均，纵轴为绝对气温 global_tmean） |
| `annual_temperature_trend.png` | 图2：全球历年平均气温趋势（年值 + 10 年滑动平均） |
| `march_temperature_increase.png` | 图3：3 月气温年代增幅。左=相邻十年均值之差（后十年 − 前十年）；右=每十年内部首尾差（末年 − 首年） |
| `annual_temperature_increase.png` | 图4：年均气温年代增幅（同图3口径） |
| `fixed_subset_size_vs_start_year.png` | （其他脚本产生）固定子集规模对起始年份的敏感性诊断图 |
| `merge_diff_diagnostic.png` | （其他脚本产生）数据合并差异诊断图 |

## result/Q1（运行产生的重要数据）

| 文件 | 作用 |
|---|---|
| `berkeley_global_monthly.csv` | 输入数据：Berkeley Earth 全球月均温（date, global_tmean, global_anomaly），1850-01 ~ 2022-12 |
| `march_decadal_increase.xlsx` | 3 月气温年代统计表（sheet“数据”= 数值；sheet“说明”= 字段含义文本说明） |
| `annual_decadal_increase.xlsx` | 年均气温年代统计表（同上） |

## log/Q1（运行日志）

| 文件 | 作用 |
|---|---|
| `plot_temperature.log` | `stage_1/plot_temperature_trends.py` 的运行日志（数据范围、年代分组、统计摘要） |

## 口径备注（stage_1 绘图）

- 论文风（遵循 modelviz-skill）：Times New Roman 字体 + `pdf.fonttype=42`、ColorBrewer 配色、仅左/下轴线 + 浅网格、图片注释全英文。
- 十年分组：从 2022 年往前每 10 年一段（2022-2013, 2012-2003, …），首段 1850-1852 为不完整段（仅 3 年）。
- 趋势图纵轴：绝对气温 `global_tmean`（℃），叠加 10 年滑动平均与线性趋势线（虚线），并标注每十年升温斜率与 p 值。
- 增幅图两种口径：①相邻十年均值相减（后十年 − 前十年，首段无基准故不画）；②每十年内部首尾差（末年份 − 首年份），正值暖色 / 负值冷色。
- 可调参数集中在 `stage_1/plot_temperature_trends.py` 开头（TARGET_MONTH / ANCHOR_YEAR / ROLL_WINDOW / 正负配色键等）。
