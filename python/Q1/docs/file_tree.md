# Q1 文件架构说明

> 更新时间：预处理阶段（抓数 → 合并 → 数据字典）完成后
> 目录约定：预处理代码 `script/Q1`、预处理结果 `output/Q1`、建模代码 `python/Q1`、
> 运行时数据 `result/Q1`、图片 `image/Q1`、日志 `log/Q1`

## 一、目录结构总览

```
2022C/
├── config_pic.json                     【全局】统一绘图配色/字体/尺寸（根目录）
├── requirements.txt                    【全局】依赖及版本
│
├── data/                               题目原始资料（只读，不产出）
│   └── 2022_APMCM_C_Data.csv           题目附件，1743-11 ~ 2013-09，239177 行，latin-1 编码
│
├── script/Q1/                          【预处理代码】
│   ├── config.json                     预处理统一配置（paths / fetch / merge 三段）
│   ├── common/                         Q1 各脚本共用工具
│   │   ├── __init__.py
│   │   ├── io_utils.py                 路径解析、日志、附件读取（编码兜底/坐标解析/乱码修复）、落盘、uid 生成
│   │   └── plot_utils.py               读 config_pic.json、统一 rcParams、存图
│   ├── fetch_march2022_temperature.py  步骤1：抓 NASA POWER 气温
│   ├── merge_city_monthly.py           步骤2：附件 + POWER 逐月合并
│   └── build_data_dictionary.py        步骤3：为 output/Q1 每个 csv 生成 sheet 说明
│
├── output/Q1/                          【预处理结果】
│   ├── city_monthly_1991_2022.csv      100 点 1991-2022 逐月均温（POWER）
│   ├── march2022_city_summary.csv      100 点 2022-03 均温/气候态/距平
│   ├── march2022_city_daily.csv        100 点 2022-03 逐日 T2M/T2M_MAX/T2M_MIN
│   ├── march2022_country_summary.csv   48 国 2022-03 汇总
│   ├── headline_march2022.csv          18 个点名地点 2022-03
│   ├── headline_monthly_1981_2024.csv  18 个点名地点 1981-2024 逐月
│   ├── attachment_vs_power_bias.csv    跨源偏差诊断（附件 vs POWER）
│   ├── merged_city_monthly_1743_2022.csv  ★核心：合并后逐月长表 239368 行
│   ├── conflict_detail.csv             被判"冲突大"的 2490 个月份明细
│   ├── conflict_summary_by_city.csv    按城市的冲突统计与系统偏差
│   ├── merge_stats.csv                 合并总账（1 行）
│   ├── data_dictionary.xlsx            ★数据字典：每 csv 一个 sheet（用途/规模/字段含义）
│   ├── .gitkeep
│   └── cache/                          236 个单点原始 JSON（可删，删后重跑会重下）
│
├── python/Q1/                          【建模代码】
│   ├── check_missing.py                附件缺失值体检（独立脚本，输出到 result/Q1）
│   ├── common/
│   │   ├── __init__.py
│   │   └── model_utils.py              建模阶段共用：路径锚定、读配置、双通道日志、落盘
│   ├── stage_1/
│   │   ├── config.json                 stage_1 配置（paths + global 聚合口径）
│   │   └── compute_global_monthly.py   stage_1：按月计算全球平均气温（两口径并列）
│   ├── stage_1/                        按阶段放置建模脚本（stage_1 已完成：全球月均温聚合）
│   └── docs/file_tree.md               本文件
│
├── result/Q1/                          【建模运行时数据】
│   ├── missing_by_city.csv             各城市缺失统计（check_missing.py 产出）
│   ├── missing_by_city_detail.csv      各城市起止月份与缺失率
│   ├── missing_by_year.csv             按年缺失统计
│   ├── missing_by_decade.csv           按年代缺失统计
│   ├── missing_gaps.csv                连续缺失片段（游程）清单
│   ├── global_monthly_tmean_1891_2022.csv  ★stage_1 成果：1891-2022 逐月全球均温（1584 行）
│   └── _log.txt                        check_missing.py 的控制台输出存档
│
├── image/Q1/                           【图片】
│   └── merge_diff_diagnostic.png       左：冲突度量分布+阈值；右：城市系统偏差 vs 替换比例
│
└── log/Q1/                             【日志】
    ├── fetch_march2022.log             步骤1 日志
    ├── merge_city_monthly.log          步骤2 日志
    ├── build_data_dictionary.log       步骤3 日志
    └── stage_1_global_monthly.log      stage_1 全球月均温聚合日志
```

> `result/Q1/city_monthly_1991_2022.csv` 是手动复制的 POWER 数据副本，
> 与 `output/Q1/city_monthly_1991_2022.csv` 完全重复，**建议删除**（本文档未列入正式产物）。

## 二、三个预处理步骤

| 步骤 | 脚本 | 输入 | 输出 |
|---|---|---|---|
| 1 抓数 | `fetch_march2022_temperature.py` | 附件坐标 + NASA POWER API | `output/Q1/` 前 7 个 csv |
| 2 合并 | `merge_city_monthly.py` | 附件 + `city_monthly_1991_2022.csv` | 合并表、冲突报表、诊断图 |
| 3 字典 | `build_data_dictionary.py` | `output/Q1/*.csv` | `data_dictionary.xlsx` |

执行顺序必须是 1 → 2 → 3（步骤3 会扫描步骤1、2 的全部 csv）。

## 三、合并规则（步骤2）

| 情形 | 判定 | `source` 标记 | 最终取值 |
|---|---|---|---|
| 两源都有，冲突度量 ≤ 阈值 | 冲突小 | `attachment` | **附件原值** |
| 两源都有，冲突度量 > 阈值 | 冲突大 | `power_replace` | **POWER 值** |
| 附件缺该月（2013-10 之后等） | 无冲突可比 | `power_fill` | POWER 值 |
| POWER 无覆盖（1991-01 之前） | 无冲突可比 | `attachment_only` | 附件值 |

- 输出覆盖 **1743-11 ~ 2022-12** 全历史，共 239368 行；1991 年前占 84%（200968 行）。
- 判决阈值依据：27207 个重叠月份的 \|Δ\| 分位为 50%=0.95、90%=2.62、95%=3.51 ℃，
  故取 **±1.5 ℃**（`merge.decision.abs_diff_threshold_c`）。
- 默认模式 `bias_corrected`：先扣掉该城市的**系统偏差**（Δ 中位数）再判冲突。
  与 `absolute` 对比：替换比例 29.6% → **9.15%**，整条被替换的城市 4 → **0** 个。

当前结果：仅附件 200968 / 保留附件 24717 / 替换 2490 / 补齐 11193；因两源均无值剔除 10909。

## 四、必须写进论文的局限性

1. **附件坐标粗且偏移**（Santiago 记为 32.95S/69.89W，落在安第斯山区），
   按附件坐标取到的是附近网格而非城市中心，绝对气温会偏 1–8 ℃。
2. **跨源整体偏差 −0.69 ℃**（POWER 比附件低），见 `attachment_vs_power_bias.csv`。
   不要把 POWER 绝对气温直接接到附件拟合的绝对气温模型上；用距平做增量修正。
3. **系统偏差被有意保留**（如 Santiago 仍高 8 ℃），故**绝对气温不可跨城市比较**，
   但同一城市的距平/趋势不受影响。
4. **源混杂**：88 个城市同时含附件值与 POWER 值，`bias_corrected` 已把替换压到 9.15%。
5. **1991 年前无第二数据源可校验**，且附件自身缺测 10909 个月已剔除，
   导致每点行数不等（Lima 1633 ~ Paris 3278）。长期趋势建议给「全时段」与「1900 年后」两套结果。
6. **国家值是站点等权平均**，未做人口/面积加权。

## 五、可调参数（`script/Q1/config.json`）

| 键 | 默认 | 说明 |
|---|---|---|
| `paths.attachment_csv` | data/2022_APMCM_C_Data.csv | 题目附件路径 |
| `paths.attachment_encodings` | ["utf-8","latin-1"] | 编码兜底顺序 |
| `paths.output_dir` | output/Q1 | 预处理结果目录 |
| `paths.cache_dir` | output/Q1/cache | 抓数缓存 |
| `paths.power_monthly_csv` | output/Q1/city_monthly_1991_2022.csv | 步骤2 的 POWER 输入 |
| `paths.log_dir` / `paths.image_dir` | log/Q1 / image/Q1 | 日志与图片目录 |
| `paths.pic_config` | config_pic.json | 统一配色来源 |
| `fetch.target_month` | 2022-03 | 目标月，换月份只需改这里 |
| `fetch.baseline` | 1991–2020 | 气候态基期（WMO 30 年） |
| `fetch.city_series_range` | 1991–2022 | 附件点的 POWER 序列范围 |
| `fetch.headline_series_range` | 1981–2024 | 点名地点序列范围（POWER 最早 1981） |
| `fetch.api.max_workers` / `request_interval` | 4 / 0.15 | 并发与限速（官方约 1000 次/小时） |
| `fetch.api.use_cache` | true | 复用缓存，`--no-cache` 强制重下 |
| `fetch.headline_locations` | 18 个点 | 增删点位只改这里，不动代码 |
| `merge.window.start/end` | 1743-01 / 2022-12 | 输出总窗口（**勿裁到 1991 后，会丢 250 年历史**） |
| `merge.window.power_start/end` | 1991-01 / 2022-12 | POWER 覆盖范围 |
| `merge.decision.mode` | bias_corrected | `absolute` 按逐月 \|Δ\|；`bias_corrected` 先扣城市系统偏差 |
| `merge.decision.abs_diff_threshold_c` | 1.5 | 冲突阈值（℃），越大越偏向保留附件 |

## 六、重跑

```bash
python script/Q1/fetch_march2022_temperature.py     # 走缓存约 5 s，--no-cache 全量约 45 s
python script/Q1/merge_city_monthly.py              # 约 3 s
python script/Q1/build_data_dictionary.py           # 约 2 s
python python/Q1/stage_1/compute_global_monthly.py  # 约 3 s（建模阶段 step 1）
python python/Q1/stage_1/compute_global_monthly.py --mode att            # 仅附件，到 2013-09
python python/Q1/stage_1/compute_global_monthly.py --mode power          # 仅 POWER，1991 起
python python/Q1/stage_1/compute_global_monthly.py --power-bias global   # 抬平跨源台阶
```

> 命令行开关只临时覆盖，不改 `config.json`；结果都写到同一个
> `result/Q1/global_monthly_tmean_1891_2022.csv`，跑完想保留哪套就把
> `config.json` 的 `value_policy` 改成对应值再跑一次。

四个脚本均幂等，重复运行会覆盖同名输出。

## 七、建模阶段 stage_1：按月全球平均气温

脚本 `python/Q1/stage_1/compute_global_monthly.py`，配置 `python/Q1/stage_1/config.json`。
输入 `output/Q1/merged_city_monthly_1743_2022.csv`，输出 `result/Q1/global_monthly_tmean_1891_2022.csv`。

**两种口径并列**（同日历月内先加权、再逐月成序列）：

| 口径 | 列名 | 权重 |
|---|---|---|
| 城市等权 | `gmean_equal` | 每点权重 1 |
| 面积加权 | `gmean_coslat` | 每点权重 cos(纬度)，范围 0.496~1.000 |

**输出字段（1584 行 × 4 列，1891-01 ~ 2022-12）**：

| 字段 | 含义 |
|---|---|
| `date` | 该月 1 日，YYYY-MM-DD |
| `n_cities` | 该月参与平均的观测点数，应恒为 100（1898-02、1898-03 为 99） |
| `gmean_equal` | 全球月平均气温（城市等权，℃） |
| `gmean_coslat` | 全球月平均气温（cos(纬度) 面积加权，℃） |

**当前结果**：等权均值 19.00 ℃，面积加权 19.77 ℃（高 0.77 ℃，因低纬城市密集拉高等权值）；
1891-2022 全期线性趋势两者均为 **+0.09 ℃/10a**，两口径相关 0.9997。

**必须交代的坑：2013/2014 之交的源切换台阶。**
2013-09 之后附件断供，序列由"附件值为主"变成"全部 POWER"。而重叠期
`att_value − power_value` 的均值是 **+0.53 ℃**（POWER 系统性偏低），
等于给 2014 年之后接了一个约 −0.5 ℃ 的台阶。实测年均值：
1981-2010 为 19.44 ℃，2011-2022 反而只有 19.41 ℃，最近十年被这一台阶压平。

**取值策略开关（`global.value_policy`）**，用配置切换或命令行 `--mode/--power-bias` 临时覆盖：

| mode | 实际取列 | 时段 | 月数 | 均值 | 趋势 | 1981-2010 → 2011-2022 |
|---|---|---|---|---|---|---|
| `tmean` + 修正 `global`（**默认，主结果**） | 混合（附件为主，2014 起 POWER），POWER 段 +0.53 ℃ | 1891-01~2022-12 | 1584 | 19.04 | +0.106 | 19.47 → 19.84（台阶 +0.37，合理） |
| `tmean` + 修正 `per_city` | 同上，各城市用自身偏差 | 1891-01~2022-12 | 1584 | 19.04 | +0.106 | 19.46 → 19.83（全球平均下与 global 差 0.002 ℃） |
| `tmean` + 修正 `none`（未修正对照） | 混合，不做任何修正 | 1891-01~2022-12 | 1584 | 19.00 | +0.088 | 19.44 → 19.41（台阶 −0.02，被压平） |
| `att`（仅附件） | `att_value` | 1891-01~2013-09 | 1473 | 18.98 | +0.098 | 19.45 → 19.76 |
| `power`（仅 POWER） | `power_value` | 1991-01~2022-12 | 384 | 19.15 | +0.192 | 19.08 → 19.28 |

结论：跨源台阶未修正时全期趋势被低估约 0.02 ℃/10a，且最近十年完全看不到增温；
修正或改用单一源后趋势回到 +0.10 ℃/10a 量级。**论文正文建议给出"修正 global"主结果
+ 其余三列作敏感性对比。**

注意：`--mode att` 时 2013-09 这个月只剩 **7 个城市**（附件在该月近乎断供），
末月不可信；若要引用该策略，需手工截到 2013-08。

**stage_1 可调参数（`python/Q1/stage_1/config.json`）**：

| 键 | 默认 | 说明 |
|---|---|---|
| `global.window.start/end` | 1891-01 / 2022-12 | 聚合窗口；往前调会引入站点数增长造成的伪趋势 |
| `global.value_policy.mode` | tmean | 取值列：tmean / att / power |
| `global.value_policy.power_bias_correction` | global | POWER 段偏差修正：none / global / per_city（默认 global = 论文主结果） |
| `global.weights.equal/coslat` | true / true | 两口径开关，只开一种就只输出一列 |
| `global.decimals` | 3 | 输出小数位，与 tmean 精度一致 |
| `global.output_file` | global_monthly_tmean_1891_2022.csv | 结果文件名 |
