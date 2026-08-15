# -*- coding: utf-8 -*-
"""
企业微信群机器人推送模块（独立工具，不侵入任何现有报告脚本）
====================================================================
能力：
  · send_markdown(content)     —— 推送 Markdown 摘要
  · send_text(content)         —— 推送纯文本（可 @ 群成员）
  · send_file(file_path)       —— 推送文件附件（HTML / PDF / 图片均可）
  · push_report(html_path)     —— 自动提取摘要 + 发送 Markdown 摘要 + 发送文件附件

配置 Webhook Key（三选一，优先级从高到低）：
  1. 函数调用时通过参数 webhook_key 传入
  2. 环境变量 WECOM_WEBHOOK_KEY
  3. 同目录下 wecom_config.json 文件，内容：{"webhook_key": "xxx"}

获取 Webhook Key 步骤：
  企业微信群 → 群设置 → 群机器人 → 添加机器人 → 复制 Webhook 地址
  地址形如 https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=<这里就是 key>

限制：
  · 单条消息频率 20 条/分钟
  · 文件 ≤ 20 MB
  · Markdown ≤ 4096 字节
  · 图片 ≤ 2 MB
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, List

try:
    import requests
except ImportError:
    print("[wecom] 缺少 requests 库，请执行: pip install requests")
    raise


WEBHOOK_BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook"
CONFIG_FILE = Path(__file__).parent / "wecom_config.json"


# ════════════════════════════════════════════════════════════════════
# 配置加载
# ════════════════════════════════════════════════════════════════════

def load_webhook_key(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit.strip()
    env = os.environ.get("WECOM_WEBHOOK_KEY")
    if env:
        return env.strip()
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            k = cfg.get("webhook_key", "").strip()
            if k:
                return k
        except Exception as e:
            print(f"[wecom] 警告：读取 {CONFIG_FILE.name} 失败：{e}")
    raise RuntimeError(
        "未找到企业微信 Webhook Key。请通过下列任一方式配置：\n"
        "  1) 设置环境变量 WECOM_WEBHOOK_KEY\n"
        f"  2) 在 {CONFIG_FILE} 中写入 {{\"webhook_key\": \"你的key\"}}\n"
        "  3) 调用时通过 webhook_key 参数传入"
    )


# ════════════════════════════════════════════════════════════════════
# 基础推送原语
# ════════════════════════════════════════════════════════════════════

def _post(url: str, payload: Dict, timeout: int = 15) -> Dict:
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"企业微信接口错误：{data}")
    return data


def send_text(content: str, mentioned_list: Optional[List[str]] = None,
              webhook_key: Optional[str] = None) -> Dict:
    """推送纯文本。mentioned_list 可填用户 ID 或 @all。"""
    key = load_webhook_key(webhook_key)
    url = f"{WEBHOOK_BASE}/send?key={key}"
    payload = {"msgtype": "text", "text": {"content": content}}
    if mentioned_list:
        payload["text"]["mentioned_list"] = mentioned_list
    return _post(url, payload)


def send_markdown(content: str, webhook_key: Optional[str] = None) -> Dict:
    """推送 Markdown。注意企业微信 Markdown 是简化版，不支持图片，长度 ≤ 4096 字节。"""
    key = load_webhook_key(webhook_key)
    url = f"{WEBHOOK_BASE}/send?key={key}"
    # 企业微信 markdown 单条限制 4096 字节，超长截断并提示
    encoded = content.encode("utf-8")
    if len(encoded) > 4000:
        truncated = encoded[:3900].decode("utf-8", errors="ignore")
        content = truncated + "\n\n> ⚠ 摘要过长已截断，完整内容见附件。"
    return _post(url, {"msgtype": "markdown", "markdown": {"content": content}})


def send_file(file_path: str, webhook_key: Optional[str] = None) -> Dict:
    """推送文件附件。先上传 → 拿 media_id → 发送 file 消息。"""
    key = load_webhook_key(webhook_key)
    fp = Path(file_path)
    if not fp.exists():
        raise FileNotFoundError(f"文件不存在：{fp}")
    size = fp.stat().st_size
    if size > 20 * 1024 * 1024:
        raise ValueError(f"文件过大 ({size/1024/1024:.1f} MB)，企业微信限制 20 MB 以内")
    if size < 5:
        raise ValueError("文件过小（< 5 字节），企业微信会拒绝")

    upload_url = f"{WEBHOOK_BASE}/upload_media?key={key}&type=file"
    with open(fp, "rb") as f:
        files = {"media": (fp.name, f, "application/octet-stream")}
        r = requests.post(upload_url, files=files, timeout=60)
    r.raise_for_status()
    data = r.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"上传文件失败：{data}")
    media_id = data["media_id"]

    send_url = f"{WEBHOOK_BASE}/send?key={key}"
    return _post(send_url, {"msgtype": "file", "file": {"media_id": media_id}})


# ════════════════════════════════════════════════════════════════════
# 从 HTML 报告提取摘要（不侵入已有脚本）
# ════════════════════════════════════════════════════════════════════

REPORT_TYPE_HINTS = [
    # (匹配关键字, 报告中文名, emoji)
    ("场景化交易剧本", "场景化交易剧本", "🎯"),
    ("市场深度分析简报", "市场深度分析简报", "🔍"),
    ("PA × Elliott", "PA × 艾略特双引擎融合", "⚡"),
    ("艾略特波浪", "艾略特波浪分析", "🌊"),
    ("价格行为", "价格行为分析", "📐"),
    ("综合分析", "黄金综合分析", "📊"),
]


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def parse_report(html_path: str) -> Dict:
    """
    从已生成的 HTML 报告中解析关键字段。
    解析逻辑基于本项目所有报告通用的标记：
      · <title>...</title>
      · 数据源：<b>...</b>
      · 当前价：<b>...</b>
      · 报告时间：<b>...</b>
    """
    text = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    info: Dict = {"file": str(Path(html_path).resolve())}

    m = re.search(r"<title>(.*?)</title>", text, re.S)
    info["title"] = _strip_tags(m.group(1)) if m else Path(html_path).stem

    m = re.search(r"数据源[：:][\s\S]*?<b>([^<]+)</b>", text)
    info["source"] = m.group(1).strip() if m else "未知"

    m = re.search(r"当前价[：:][\s\S]*?<b>([^<]+)</b>", text)
    info["current_price"] = m.group(1).strip() if m else "—"

    m = re.search(r"报告时间[：:][\s\S]*?<b>([^<]+)</b>", text)
    info["report_time"] = m.group(1).strip() if m else ""

    # 报告类型与图标
    info["type_zh"] = "黄金行情报告"
    info["icon"] = "📈"
    for kw, zh, icon in REPORT_TYPE_HINTS:
        if kw in info["title"] or kw in text[:5000]:
            info["type_zh"] = zh
            info["icon"] = icon
            break

    # 提取核心叙事 / 综合判断（针对 SMC 简报、剧本、融合报告，提取首段叙事）
    info["highlights"] = []
    # 匹配 class="text" 或 class="narrative" 或 .stance .text 内的第一个段落文本
    for pat in [
        r'<div class="exec-summary">[\s\S]*?<div class="text">([\s\S]*?)</div>',
        r'<div class="stance">[\s\S]*?<div class="text">([\s\S]*?)</div>',
        r'<div class="narrative">([\s\S]*?)</div>',
        r'<div class="verdict-card">([\s\S]*?)</div>',
    ]:
        m = re.search(pat, text)
        if m:
            raw = _strip_tags(m.group(1))
            # 取前 3 句（按句号、问号、感叹号分句）
            sentences = re.split(r"[。！？]", raw)
            sentences = [s.strip() for s in sentences if s.strip()]
            info["highlights"] = sentences[:3]
            break

    return info


def build_summary_markdown(info: Dict) -> str:
    """根据解析结果构造企业微信 markdown 摘要。"""
    lines = []
    lines.append(f"## {info['icon']} {info['type_zh']}")
    lines.append("")
    lines.append(f"> **数据源**：{info['source']}")
    lines.append(f"> **当前价**：<font color=\"warning\">{info['current_price']}</font>")
    lines.append(f"> **报告时间**：{info['report_time']}")
    lines.append("")
    if info["highlights"]:
        lines.append("**核心要点：**")
        for s in info["highlights"]:
            # 截断单条过长（企业微信 markdown 阅读体验）
            if len(s) > 120:
                s = s[:117] + "..."
            lines.append(f"- {s}")
        lines.append("")
    lines.append("> 完整报告请查看下方附件 ⬇")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
# 一站式：摘要 + 文件
# ════════════════════════════════════════════════════════════════════

def push_report(html_path: str, webhook_key: Optional[str] = None,
                send_summary: bool = True, send_attachment: bool = True,
                interval: float = 1.0) -> None:
    """
    把一份 HTML 报告完整推送到企业微信群。
      1. 先发 Markdown 摘要
      2. 等待 1 秒（避免触发频控）
      3. 再发 HTML 文件附件
    """
    fp = Path(html_path)
    if not fp.exists():
        raise FileNotFoundError(f"报告文件不存在：{fp}")

    info = parse_report(str(fp))
    print(f"[wecom] 解析报告：{info['type_zh']} · {info['title']}")

    if send_summary:
        md = build_summary_markdown(info)
        print(f"[wecom] 推送 Markdown 摘要 ({len(md)} 字符)...")
        send_markdown(md, webhook_key=webhook_key)
        print("[wecom] ✓ 摘要推送成功")
        time.sleep(interval)

    if send_attachment:
        size_kb = fp.stat().st_size / 1024
        print(f"[wecom] 推送文件附件 {fp.name} ({size_kb:.1f} KB)...")
        send_file(str(fp), webhook_key=webhook_key)
        print("[wecom] ✓ 文件推送成功")


# ════════════════════════════════════════════════════════════════════
# 自检入口
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 自检：尝试加载 key 并发送一条测试文本
    try:
        key = load_webhook_key()
        print(f"[wecom] 已加载 Webhook Key（前 8 位）：{key[:8]}...")
    except RuntimeError as e:
        print(f"[wecom] 配置异常：\n{e}")
        sys.exit(1)
    print("[wecom] 发送测试消息...")
    send_text("企业微信推送通道自检 ✅ —— 来自黄金分析系统")
    print("[wecom] 自检完成，请到企业微信群查看测试消息。")
