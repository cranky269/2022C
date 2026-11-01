# -*- coding: utf-8 -*-
"""Q1 建模阶段通用工具：路径锚定、配置读取、双通道日志、结果落盘。

与预处理阶段的 script/Q1/common/io_utils.py 有意分开：预处理那套里有附件编码兜底、
坐标解析等抓数专用逻辑，建模阶段用不上；这里只保留最小集合，避免跨阶段耦合。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]   # python/Q1/common -> 2022C


# --------------------------------------------------------------------------- #
# 路径与配置
# --------------------------------------------------------------------------- #
def resolve_path(path_str: str | Path) -> Path:
    """把配置里的相对路径锚定到项目根目录，绝对路径原样返回。"""
    path = Path(path_str)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_json(path_str: str | Path) -> dict[str, Any]:
    """读取 JSON 配置，文件不存在时直接报错（早失败好过静默用默认值）。"""
    path = resolve_path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# 日志与落盘
# --------------------------------------------------------------------------- #
def setup_logger(log_path: str | Path, name: str) -> logging.Logger:
    """双通道日志（文件覆盖写 + 控制台），重复调用时重置 handler。"""
    path = resolve_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.FileHandler(path, mode="w", encoding="utf-8"),
                    logging.StreamHandler(sys.stdout)):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def save_csv(frame: pd.DataFrame, path_str: str | Path, logger: logging.Logger) -> Path:
    """统一落盘（UTF-8-BOM，Excel 直接可读），返回实际写入路径。"""
    path = resolve_path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info("已写出 %s  (%d 行 × %d 列)",
                path.relative_to(PROJECT_ROOT), len(frame), frame.shape[1])
    return path
