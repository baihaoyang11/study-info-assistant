# Academic Mail Agent · 第一阶段

QQ 只读 IMAP 邮件头工具，默认运行离线 Mock。仅获取最近最多 10 封邮件的 Date、From、Subject、Message-ID；不读正文/附件，不发送、不标记已读、不移动、不删除。沿用 [已有开源评估](docs/open_source_evaluation.md)，没有复制其中七个项目的代码。

本阶段仅实现 Python CLI；Canvas 仅有接口与固定课程 Mock。课程提取、分类、SQLite、摘要和其他邮箱留待后续阶段。

代码仓库：[study-info-assistant](https://github.com/baihaoyang11/study-info-assistant)。后续开发以通过测试的功能提交同步；GitHub Actions 在 Python 3.11/3.12/3.13 上运行离线测试。私有配置、数据、输出和日志不提交。

2026-10-12 已在当前 Codex 聊天创建半日自动任务（北京时间 09:00、21:00），当前为邮件头候选事项检查试运行：只覆盖最近 10 封邮件头，不能保证覆盖全部新邮件，也不能从主题可靠提取正文中的截止时间。Canvas 尚未接入。任务不是常驻邮箱守护进程，自动执行依赖本机和桌面应用运行及所需网络权限。完整自主待办目标与剩余接入信息见 [路线图](docs/agent_roadmap.md)。

## 安装

Python 3.11+，PowerShell：

```powershell
Set-Location D:\academic-mail-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

本次开发环境使用 Codex 自带 Python 3.12.14 和已安装的 Pydantic 2.13.5，并在项目 `.venv` 放置 pytest 9.1.1 与 python-dotenv 1.2.4。该环境引用本机 Codex 运行时；换机时请按以上命令重建，不复制 `.venv`。

## 离线使用（已授权，可直接运行）

```powershell
.\.venv\Scripts\academic-mail-agent.exe
.\.venv\Scripts\academic-mail-agent.exe list
.\.venv\Scripts\academic-mail-agent.exe list --detail
.\.venv\Scripts\academic-mail-agent.exe diagnose
.\.venv\Scripts\academic-mail-agent.exe --help
```

输出 JSON。默认隐藏所有主题；`--detail` 显示主题并在 stderr 提示隐私。发件人、Message-ID 和日期仍是个人数据，仅供本地展示。邮件内容作为不可信文本，不执行指令或链接，不上传外部 AI 服务，不自动写文件或记录日志。

## 真实邮箱：已完成授权只读验收

2026-10-12，用户确认后已完成真实 QQ 邮箱连接：通过 TLS 与认证，成功读取最近 3 封邮件的指定头字段，随后断开连接。未读取正文或附件，未发送邮件或执行写操作。验收未保存邮件内容。

本机 `.env` 已配置账号和 IMAP 授权码，不在文档中记录凭证。其他机器可按 `.env.example` 配置 `QQ_EMAIL`、`QQ_IMAP_AUTH_CODE`（QQ 的 IMAP 授权码，非登录密码）、`QQ_IMAP_TIMEOUT`（秒，默认 15，范围 0 < timeout <= 120）。`.env` 已加入忽略清单；环境变量优先于文件，只读指定文件或当前目录 `.env`，不查找父目录，不插值、不修改环境变量。

```powershell
# 已授权的只读读取，默认隐藏主题：
.\.venv\Scripts\academic-mail-agent.exe list --provider qq --allow-real-mailbox --limit 3
```

缺少 `--allow-real-mailbox` 时，在读取配置或构造连接之前退出。连接器 `connect()` 同样默认拒绝真实连接，必须显式 `allow_real=True`。这是操作授权门，邮箱侧 QQ 授权码本身并不是只读权限；只读限制由本程序的窄接口、EXAMINE/PEEK 和测试保证。

固定 `imap.qq.com:993`，使用默认安全 TLS 上下文，校验证书与主机名；INBOX 只读选择；以 UID 排序去重，从大到小最多 10 封。Date 缺失、无时区或坏格式返回 unknown；不会推断时区。坏服务器响应受控失败，UID FETCH 返回 ID 必须匹配请求。连接结束仅 logout/必要 shutdown，不使用 CLOSE。

退出码：0 成功，2 授权/配置/网络/协议/参数错误，130 用户中断。错误仅输出固定错误码与说明，不输出原始服务器异常或凭证。没有自动重试和增量同步。

## 离线验收

```powershell
# 若沙箱临时目录/中文路径存在兼容问题，使用项目内临时目录：
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TMP = (Resolve-Path .tmp).Path
$env:TEMP = $env:TMP
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pytest -q
```

pytest 自动阻断 socket 连接，协议测试只注入 Fake IMAP，不使用真实账号。另已完成一次用户授权的 QQ 真实只读验收；该验收不属于自动测试，也不代表长期同步或服务器所有响应均已验证。

打包：`python -m pip wheel --no-deps --wheel-dir dist .`。详细结果见 `docs/phase1_validation.md`。

参考协议语义：[Python 官方 imaplib 文档](https://docs.python.org/3/library/imaplib.html)。
