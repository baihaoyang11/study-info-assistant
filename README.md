# Academic Mail Agent / Study Info Assistant · 0.2.0

QQ 邮件正文只读采集 → 本机 SQLite → 学业事项提取 → CLI 清单。默认离线 Mock；Canvas 只接受本地 TXT/Markdown，不连接学校平台。沿用 [开源评估](docs/open_source_evaluation.md)，没有复制被评估项目代码。原有邮件头 CLI 与 Mock 保留。

代码：[study-info-assistant](https://github.com/baihaoyang11/study-info-assistant)。通过测试的里程碑同步 GitHub；真实邮件、Canvas 内容、凭证、数据库与摘要不提交。

## 安装

Python 3.11+，PowerShell：

```powershell
Set-Location D:\academic-mail-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

本机使用 Python 3.12.14、Pydantic 2.13.5、pytest 9.1.1、python-dotenv 1.2.4。`.venv` 引用本机 Codex 运行时，换机请重建。

## 离线使用

```powershell
# 演示与真实数据使用不同数据库
.\.venv\Scripts\python.exe -m academic_mail_agent sync --db data/mock.sqlite3
.\.venv\Scripts\python.exe -m academic_mail_agent import-canvas examples/canvas-note.md --source-name "演示课程页面" --db data/mock.sqlite3
.\.venv\Scripts\python.exe -m academic_mail_agent todos --db data/mock.sqlite3
.\.venv\Scripts\python.exe -m academic_mail_agent digest --db data/mock.sqlite3
.\.venv\Scripts\python.exe -m academic_mail_agent todos --format json --db data/mock.sqlite3
```

清单保留课程、类型、来源引用、原文证据、截止日期/时区、待核对原因、完成状态，按逾期、未来七天、待核对和其他事项分组。默认隐藏已完成事项；`--include-done` 单独展示已完成分组。

```powershell
# 替换为清单显示的 ID，只修改本机完成状态
.\.venv\Scripts\python.exe -m academic_mail_agent complete ITEM_ID --db data/mock.sqlite3
.\.venv\Scripts\python.exe -m academic_mail_agent complete ITEM_ID --reopen --db data/mock.sqlite3
```

## QQ 正文只读采集

本机 `.env` 已配置；其他机器按 `.env.example` 设置 `QQ_EMAIL`、`QQ_IMAP_AUTH_CODE` 和 `QQ_IMAP_TIMEOUT`。凭证不写入文档、数据库或输出。环境变量优先，只加载显式文件或当前目录 `.env`，不搜索父目录、不插值。

```powershell
.\.venv\Scripts\python.exe -m academic_mail_agent sync --provider qq --allow-real-mailbox --limit 50 --env-file .env --db data/study.sqlite3
.\.venv\Scripts\python.exe -m academic_mail_agent todos --db data/study.sqlite3
.\.venv\Scripts\python.exe -m academic_mail_agent digest --db data/study.sqlite3
```

`sync` 默认最近 50 封，可选 1–100。固定 TLS `imap.qq.com:993`，验证证书和主机名，以只读 INBOX 与 UID `BODY.PEEK` 读取指定邮件头和文本 part。解析 BODYSTRUCTURE，跳过附件、带文件名的文本和嵌套邮件；HTML 转纯文本，不打开图片/链接。单 part 最多 256 KiB，单邮件文本最多 1 MiB，最多 32 个 part；超过限制或解码不完整标为待核对。正文与事项只保存在本机数据库。

来源键含账号散列、INBOX、UIDVALIDITY、UID；重复来源更新，正文与事项同一事务写入。同一可识别事项更新截止时间时保留完成状态。失败不覆盖已存正文，清单展示最近结果与范围。**本版是最近窗口采集，不是完整增量/全部历史同步。**

缺少 `--allow-real-mailbox` 时，在加载凭证或创建数据库前拒绝连接。QQ 授权码本身具有写权限；程序通过窄命令接口、EXAMINE/PEEK 与测试保持只读。不发送、标记已读、移动或删除邮件。

2026-10-12 已在用户授权下成功验证最近 3 封真实 QQ 文本正文，本机保存来源与清单；这不代表全部邮箱或长期同步已验收。

## Canvas 手动入口

学校尚未允许外部接入。本版不调用 Canvas API，不自动操作浏览器。将有权查看的作业/公告文字保存为 UTF-8 `.txt` 或 `.md`：

```powershell
.\.venv\Scripts\python.exe -m academic_mail_agent import-canvas D:\notes\COMP101.md --source-name "COMP101 作业页面" --db data/study.sqlite3
```

文件最多 1 MiB；同一路径重新导入更新原来源，不同页面请使用不同路径。保留人工来源名与导入时间，没有自动核对远端变动。暂不支持 PDF、截图/OCR 或附件。

## 提取与隐私边界

本地规则识别关键词及完整数字年月日，例如 `2026-10-20`、`2026年10月20日`。作业/通知有截止标识才确定截止日期，考试可识别发生时间；明确时区才生成时间点。相对日期、英文月份、无年份/时区、多个候选日期、取消/延期或不完整正文需人工核对。规则可能漏提/误提，不保证覆盖全部学业事项。相同无区分名称的多个事项使用出现次序区分，编辑手动文件后需核对完成状态。

不上传正文到外部模型，不执行邮件指令/链接。SQLite 是本机明文文件，清单包含原文证据，请按私有资料保管。`data/`、`.env`、日志与构建产物均忽略。`todos`/`digest` 只读本地数据，不联网。

既有半日桌面任务仍是最近 10 封邮件头试运行；本次未升级定时任务，也未验证实际定时执行。没有常驻服务或 SMTP 送达模块。见 [路线图](docs/agent_roadmap.md)。

## 兼容命令与验证

`list` 保留最近 1–10 封邮件头读取，默认隐藏主题，`--detail` 本地显示；`diagnose` 不加载凭证、不联网；`--help` 查看全部命令。

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TMP = (Resolve-Path .tmp).Path
$env:TEMP = $env:TMP
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation --wheel-dir dist .
```

pytest 阻断 socket，仅用合成正文、Fake IMAP 和临时数据库；CI 在 Python 3.11/3.12/3.13 跑离线测试。退出码：0 成功，2 固定错误码/说明，130 用户中断；不输出服务器原始异常或授权码。见 [阶段二验收](docs/phase2_validation.md)、[阶段一记录](docs/phase1_validation.md)。
