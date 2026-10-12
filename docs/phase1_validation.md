# 第一阶段验收：离线测试与授权真实连接

日期：2026-10-12（Asia/Shanghai）。项目：D:\academic-mail-agent。

## 已完成

- QQ 只读 IMAP 连接器：显式授权门、固定 TLS 地址、证书/主机名验证、只读 INBOX、数值 UID 去重排序、最近最多 10 封、PEEK 指定邮件头、退出清理。
- CLI：默认 Mock、无网络 diagnose、显式 detail 隐私提示、固定错误码和退出码；配置仅在真实命令授权后读取。
- 离线 Mock、Pydantic 元数据、MIME/日期安全解析；Canvas 仅接口和固定课程 Mock。

## 验证证据

Python 3.12.14、Pydantic 2.13.5、python-dotenv 1.2.4、pytest 9.1.1。

完整测试命令：`.\.venv\Scripts\python.exe -m pytest -q`；TMP/TEMP 指向项目 `.tmp`，PYTHONUTF8=1。

结果：**56 passed**。覆盖只读请求与命令白名单、UID 边界/去重/排序、空箱、TLS/超时/认证/协议错误、返回 UID 不匹配（包括 UID 位于 literal 后）、非法授权码、MIME/坏日期/无时区、终端控制字符、凭证不出现在显示错误中、默认无网络、配置文件作用范围、默认主题隐藏、Ctrl+C 与 logout 失败清理。

测试最初因缺少实现报 ModuleNotFoundError；实现后首轮 38 passed。新增配置/CLI 测试后有 3 项临时目录 fixture 错误，定位为中文路径乱码和沙箱临时目录访问问题；改用项目内临时目录与 UTF-8 后完整套件 51 passed。没有通过删除失败测试解决问题。

独立审查发现并修复两项 P2：合法 FETCH 的 UID 可以位于 header literal 之后；非 ASCII 授权码可能在 imaplib 中触发未净化编码异常。两项均先复现失败的回归测试，再修复；完整套件增加至 56 passed。

已实际执行并检查：

- 安装后的 `academic-mail-agent.exe diagnose`、默认 `list`、`list --detail`。
- `list --provider qq`：未传授权开关，固定错误 REAL_CONNECTION_DISABLED，退出码 2；未读真实配置、未连接邮箱。
- `python -m compileall -q src`：退出码 0。
- editable 安装：成功；wheel 构建：成功。
- wheel 安装到独立检查目录，确认从该目录导入并执行 diagnose 成功。

产物：`dist/academic_mail_agent-0.1.0-py3-none-any.whl`。

SHA256：`df004e7c482265982d2aad837a45370476d3692f4ffc197a6d32e11e45e06eae`。

审查复核：上述两项修复均已由独立审查确认解决，未发现这些修复中的剩余阻塞项。

## 交付边界

自动协议测试使用合成数据与 Fake IMAP；pytest fixture 阻断 socket 连接。离线阶段没有连接真实邮箱。后续用户明确要求配置账号并连接真实邮箱，本机 `.env` 已配置并通过本地校验，随后完成下述真实验收。没有调用 Canvas、邮件发送工具或外部 AI API。

QQ 授权码自身不限制为只读，安全边界由本实现保障。没有增量同步、UIDVALIDITY 游标、正文/附件、数据库或课程抽取。

原调研报告完整保留，报告末尾关于 D 盘不可写的描述是此前会话状态。本次用户修复 Windows 目录 ACL 后，D 盘写入已恢复。尚未创建 Git 仓库或提交。

## 授权真实验收

日期：2026-10-12（Asia/Shanghai）。用户已明确授权配置本机凭证及连接真实 QQ 邮箱。

调用现有 CLI：`list --provider qq --allow-real-mailbox --limit 3 --env-file D:\academic-mail-agent\.env`。输出在内存捕获，仅报告读取数量，不落盘保存邮件元数据、不回显凭证或主题。

首轮受沙箱网络限制返回固定 NETWORK_ERROR；获准执行同一只读操作后，结果为 `connected_and_readonly_fetch_completed`、`messages_read: 3`、`connection_closed: true`，退出码 0。

已验证真实 TLS 连接、认证、只读 INBOX、UID SEARCH/FETCH 和 CLI 退出清理在本次 QQ 响应下正常。请求只含指定邮件头；没有读取正文/附件，没有发送、删除、移动或标记命令。未独立对比读取前后的服务器 flags，因而不把未读状态不变称为实测结论；只读与 PEEK 限制有离线协议测试支持。

第一阶段与本次授权真实验收均已完成。用户随后要求持续推进；第二阶段范围待明确，不重复要求已获授权的操作。
