# 企业微信报告推送 · 使用说明

本工具将本系统生成的任意 HTML 报告自动推送到企业微信群，包含：

1. **Markdown 摘要消息** —— 报告类型、当前价、数据源、时间、核心要点
2. **HTML 文件附件** —— 完整报告，群成员点击下载即可查看

> 不侵入任何已有报告脚本，已有报告生成流程不受影响。

---

## 一、首次配置（仅需一次）

### 1. 在企业微信群中获取机器人 Webhook

1. 打开目标企业微信群
2. 群设置 → 群机器人 → 添加机器人
3. 复制机器人的 Webhook URL，形如：
   ```
   https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=<你的 KEY>
   ```
4. 把 `key=` 后面那一段（例如 `abcd1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx`）记录下来

### 2. 配置 Key（三种方式任选其一）

**方式 A · 配置文件（推荐）**

复制 `wecom_config.example.json` 为 `wecom_config.json`，填入你的 key：
```json
{
  "webhook_key": "abcd1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**方式 B · 环境变量**

PowerShell：
```powershell
$env:WECOM_WEBHOOK_KEY = "abcd1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

CMD：
```cmd
set WECOM_WEBHOOK_KEY=abcd1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**方式 C · 命令行参数**

执行时传 `--key abcd1234-...`（不推荐，会留在历史记录中）

### 3. 安装依赖（如尚未安装）

```bash
pip install requests
```

### 4. 自检

```bash
python wecom_push.py
```

应在企业微信群看到 "企业微信推送通道自检 ✅" 的消息。

---

## 二、推送报告

### 方式 A · 双击 bat（最简单，交互式选择）

双击 `run_push_to_wecom.bat`，在终端中显示所有可推送报告，输入编号即可。

### 方式 B · 自动找最新一份

```bash
python push_to_wecom.py --latest
```

### 方式 C · 按报告类型自动找最新

```bash
python push_to_wecom.py --type playbook    # 场景化交易剧本
python push_to_wecom.py --type snapshot    # 市场深度分析简报
python push_to_wecom.py --type fusion      # PA × 艾略特双引擎融合
python push_to_wecom.py --type elliott     # 艾略特波浪
python push_to_wecom.py --type wave        # 价格行为
python push_to_wecom.py --type gold        # 黄金综合分析
```

### 方式 D · 推送指定文件

```bash
python push_to_wecom.py "e:\path\to\any_report.html"
```

### 可选参数

```bash
--no-summary    # 仅发文件，不发 Markdown 摘要
--no-file       # 仅发摘要，不发文件附件
--key <KEY>     # 临时指定 webhook key
```

---

## 三、整合到现有报告流程（可选）

如想报告生成后自动推送，编辑对应的 `run_*.bat`，在最后加一行：

```bat
"F:\python-manager-26.0 (1)\python.exe" "%~dp0push_to_wecom.py" --type playbook
```

例如把 `run_scenario_playbook.bat` 改成：

```bat
@echo off
"F:\python-manager-26.0 (1)\python.exe" "%~dp0scenario_playbook_mt5.py"
"F:\python-manager-26.0 (1)\python.exe" "%~dp0push_to_wecom.py" --type playbook
pause
```

---

## 四、限制说明

| 项目 | 限制 |
|---|---|
| 单条消息频率 | 20 条 / 分钟 / 机器人 |
| 文件大小 | 5 字节 ~ 20 MB |
| Markdown 长度 | ≤ 4096 字节（超长自动截断并附提示） |
| 支持的文件类型 | 不区分，但企业微信客户端不会预览 HTML，需下载后用浏览器打开 |

---

## 五、常见问题

**Q：摘要里 "核心要点" 是空的？**
A：报告里没有匹配到 `<div class="exec-summary">` / `<div class="stance">` 等标记，例如老的 `gold_analysis` 报告。文件附件依然会正常发送。

**Q：群里看不到 HTML 预览？**
A：企业微信客户端确实不预览 HTML，群成员点击下载到本地后用浏览器打开即可。如需预览，可改用 "图片截图" 方案（需要 Playwright），告诉我后我帮你加上。

**Q：报错 "errcode 45009 / 45033"？**
A：触发频控了。脚本默认在摘要与附件之间间隔 1 秒，如多份报告连发请加大间隔或分批推送。

**Q：报错 "errcode 93000"？**
A：webhook key 错误或机器人已被移除，请重新创建机器人并更新 key。
