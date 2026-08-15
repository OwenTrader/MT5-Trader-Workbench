# -*- coding: utf-8 -*-
"""
Elliott Wave 专项 · MT5 数据源入口
====================================================================
数据回退链：MT5 (Python 包) → MT4 (CSV 借用) → Yahoo Finance
报告输出   ：reports/elliott/elliott_mt5_<时间戳>.html  + elliott_mt5_latest.html

与 wave_analysis_mt5.py / wave_analysis.py 完全互不干扰，仅做艾略特波浪专项。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from gold_analysis import fetch_data_mt5_first
from elliott_wave import run_elliott_analysis


def main():
    return run_elliott_analysis(
        fetch_fn=fetch_data_mt5_first,
        report_prefix="elliott_mt5",
        report_subdir="elliott",
        system_label="MT5 系统",
    )


if __name__ == "__main__":
    main()
