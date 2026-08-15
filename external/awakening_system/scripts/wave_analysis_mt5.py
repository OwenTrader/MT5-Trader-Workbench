# -*- coding: utf-8 -*-
"""
MT5 系统入口（独立于 MT4 系统）
================================================
数据源回退链：MT5 (Python 包) → MT4 (CSV 借用) → Yahoo Finance
报告输出   ：reports/mt5/wave_mt5_<时间戳>.html  +  wave_mt5_latest.html

与 wave_analysis.py 完全互不干扰。MT4 系统仍走 wave_analysis.py，报告在 reports/。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from gold_analysis import fetch_data_mt5_first
from wave_analysis import run_analysis


def main():
    return run_analysis(
        fetch_fn=fetch_data_mt5_first,
        report_prefix="wave_mt5",
        report_subdir="mt5",
        system_label="MT5 系统",
    )


if __name__ == "__main__":
    main()
