# -*- coding: utf-8 -*-
"""统一绘图配置加载与样式应用（Q1 通用）。

读取项目根目录 config_pic.json，并把其中的配色/字体/尺寸等应用到 matplotlib。
所有画图脚本都应从这里取样式，禁止在代码里硬编码颜色。
"""
import json
import os

import matplotlib.pyplot as plt

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_PATH = os.path.join(BASE, "config_pic.json")


def load_pic_config():
    """读取根目录 config_pic.json，返回配置字典。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def apply_mpl_style(cfg=None):
    """把配置中的字体/字号等应用到 matplotlib 全局 rcParams，返回配置字典。"""
    if cfg is None:
        cfg = load_pic_config()

    font = cfg.get("font_family", "Times New Roman")
    axes = cfg.get("axes", {})
    save = cfg.get("save", {})
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = [font, "Times New Roman", "DejaVu Serif"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = cfg.get("font_size", 11)
    plt.rcParams["axes.labelsize"] = axes.get("labelsize", 12)
    plt.rcParams["axes.titlesize"] = axes.get("titlesize", 13)
    plt.rcParams["figure.dpi"] = cfg.get("figure", {}).get("dpi", 300)
    plt.rcParams["pdf.fonttype"] = save.get("pdf_fonttype", 42)
    plt.rcParams["ps.fonttype"] = save.get("ps_fonttype", 42)
    return cfg


def palette(cfg=None):
    """返回配色字典。"""
    if cfg is None:
        cfg = load_pic_config()
    return cfg.get("palette", {})
