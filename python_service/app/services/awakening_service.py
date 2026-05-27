from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any, Callable

from python_service.app.services.ai_technical_analysis_service import generate_ai_analysis


def _get_awakening_scripts_dir() -> Path:
    current_file = Path(__file__).resolve()
    candidate_roots = (
        current_file.parents[2],
        current_file.parents[3],
    )

    for root_dir in candidate_roots:
        candidate = root_dir / 'external' / 'awakening_system' / 'scripts'
        if candidate.is_dir():
            return candidate

    return candidate_roots[0] / 'external' / 'awakening_system' / 'scripts'


AWAKENING_SCRIPTS_DIR = _get_awakening_scripts_dir()


@lru_cache(maxsize=1)
def _load_awakening_runtime() -> dict[str, Any]:
    is_frozen = getattr(sys, 'frozen', False)

    if not AWAKENING_SCRIPTS_DIR.is_dir() and not is_frozen:
        raise RuntimeError(f'Awakening scripts directory not found: {AWAKENING_SCRIPTS_DIR}')

    if AWAKENING_SCRIPTS_DIR.is_dir() and str(AWAKENING_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(AWAKENING_SCRIPTS_DIR))

    try:
        gold_analysis = importlib.import_module('gold_analysis')
        wave_analysis = importlib.import_module('wave_analysis')
        elliott_wave = importlib.import_module('elliott_wave')
        pa_wave_fusion = importlib.import_module('pa_wave_fusion')
        smc_snapshot = importlib.import_module('smc_snapshot')
        scenario_playbook = importlib.import_module('scenario_playbook')
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Failed to load awakening module '{exc.name}' from {AWAKENING_SCRIPTS_DIR}"
        ) from exc

    return {
        'report_dir': Path(gold_analysis.REPORT_DIR),
        'run_gold_analysis': gold_analysis.run_gold_analysis,
        'fetch_data_mt5_first': gold_analysis.fetch_data_mt5_first,
        'run_analysis': wave_analysis.run_analysis,
        'run_elliott_analysis': elliott_wave.run_elliott_analysis,
        'run_fusion_analysis': pa_wave_fusion.run_fusion_analysis,
        'run_snapshot': smc_snapshot.run_snapshot,
        'run_playbook': scenario_playbook.run_playbook,
    }


def _read_report_html(path: str | None) -> str:
    if not path:
        return '<div class="aw-error">该模块未生成报告。</div>'

    report_path = Path(path)
    if not report_path.exists():
        return f'<div class="aw-error">报告文件不存在：{escape(str(report_path))}</div>'

    return report_path.read_text(encoding='utf-8')


def _build_combined_html(symbol: str, sections: list[dict[str, str]], generated_at: str) -> str:
    nav_links = ''.join(
        f'<a href="#{section["anchor"]}">{escape(section["title"])}</a>'
        for section in sections
    )

    body_sections = ''.join(
        f'''
        <section id="{section["anchor"]}" class="report-section">
            <div class="section-header">
                <h2>{escape(section["title"])}</h2>
                <p>{escape(section["summary"])}</p>
            </div>
            <div class="section-body">{section["html"]}</div>
        </section>
        '''
        for section in sections
    )

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(symbol)} 综合分析报告</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07111f;
      --panel: #0d1b2a;
      --panel-2: #10243a;
      --text: #e8f0ff;
      --muted: #97abc7;
      --line: rgba(151, 171, 199, 0.18);
      --accent: #67e8f9;
      --accent-2: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: Inter, "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top, rgba(103, 232, 249, 0.18), transparent 28%),
        linear-gradient(180deg, #06101b, #091a2c 24%, #07111f 100%);
      color: var(--text);
    }}
    .page {{
      width: min(1400px, calc(100vw - 32px));
      margin: 24px auto 80px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(103, 232, 249, 0.14), rgba(251, 191, 36, 0.10));
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
    }}
    .hero h1 {{ margin: 0; font-size: clamp(28px, 5vw, 44px); }}
    .hero p {{ margin: 10px 0 0; color: var(--muted); line-height: 1.7; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }}
    .meta span {{
      border: 1px solid var(--line);
      background: rgba(7, 17, 31, 0.45);
      color: var(--muted);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
    }}
    .toc {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .toc a {{
      text-decoration: none;
      color: var(--text);
      border: 1px solid var(--line);
      background: rgba(13, 27, 42, 0.82);
      border-radius: 16px;
      padding: 14px 16px;
      font-weight: 600;
    }}
    .toc a:hover {{ border-color: rgba(103, 232, 249, 0.35); }}
    .report-section {{
      margin-top: 20px;
      background: rgba(13, 27, 42, 0.88);
      border: 1px solid var(--line);
      border-radius: 24px;
      overflow: hidden;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
    }}
    .section-header {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(16, 36, 58, 0.95), rgba(13, 27, 42, 0.9));
    }}
    .section-header h2 {{ margin: 0; font-size: 24px; }}
    .section-header p {{ margin: 8px 0 0; color: var(--muted); }}
    .section-body {{ padding: 0; background: #fff; color: #111827; }}
    .aw-error {{
      margin: 24px;
      padding: 16px 18px;
      border-radius: 14px;
      border: 1px solid #fecaca;
      background: #fff1f2;
      color: #991b1b;
      font-weight: 600;
    }}
    @media (max-width: 768px) {{
      .page {{ width: min(100vw - 20px, 1400px); margin-top: 10px; }}
      .hero {{ padding: 20px; border-radius: 18px; }}
      .section-header {{ padding: 16px 18px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <h1>{escape(symbol)} 综合技术分析报告</h1>
      <p>本报告一次性整合指标、价格行为、艾略特波浪、PA x Wave 融合、SMC 快照和情景剧本六个模块，适合直接作为盘前或盘中总览使用。</p>
      <div class="meta">
        <span>生成时间: {escape(generated_at)}</span>
        <span>分析模块: {len(sections)} 个</span>
        <span>数据源策略: MT5 -> MT4 -> Yahoo Finance</span>
      </div>
      <nav class="toc">{nav_links}</nav>
    </section>
    {body_sections}
  </main>
</body>
</html>
'''


def _persist_combined_report(html: str, report_dir: Path) -> str:
    out_dir = report_dir / 'combined'
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M')
    report_path = out_dir / f'combined_mt5_{ts}.html'
    latest_path = out_dir / 'combined_mt5_latest.html'

    report_path.write_text(html, encoding='utf-8')
    latest_path.write_text(html, encoding='utf-8')
    return str(latest_path)


def generate_report(symbol: str):
    return generate_ai_analysis(symbol).model_dump()
