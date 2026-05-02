# -*- coding: utf-8 -*-
"""
市场深度分析简报 · MT5 数据源入口
====================================================================
数据回退链：MT5 (Python 包) → MT4 (CSV) → Yahoo Finance
报告输出   ：reports/snapshot/snapshot_mt5_<时间戳>.html  + snapshot_mt5_latest.html

与现有所有入口完全互不干扰。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from gold_analysis import fetch_data_mt5_first
from smc_snapshot import run_snapshot


def main():
    return run_snapshot(
        fetch_fn=fetch_data_mt5_first,
        report_prefix="snapshot_mt5",
        report_subdir="snapshot",
        system_label="MT5 系统",
        htf_key="h4", htf_label="H4",
        ltf_key="m15", ltf_label="M15",
    )


if __name__ == "__main__":
    main()
