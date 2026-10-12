# 第一阶段实现与验收计划

沿用 open_source_evaluation.md 的最终架构，用户已授权在 D:\academic-mail-agent 实现并在完成后暂停。无需重复设计审批；真实连接不在本次授权范围内。

目标：Python 3.11+、imaplib/email/ssl、Pydantic 2、python-dotenv、pytest；不复制七个调研项目的代码。

- [x] 写测试并确认缺失实现导致失败：TLS、只读选择、UID 排序去重、PEEK、空箱、坏响应、MIME/日期、错误净化、退出清理、CLI 授权门与默认隐私。
- [x] src/academic_mail_agent/models.py、parsing.py、config.py：仅邮件头模型与解析，SecretStr 凭证；配置只在显式真实命令授权后读取。
- [x] qq_imap.py：固定 imap.qq.com:993；connect(allow_real=False) 默认阻止联网；latest_headers(limit=10) 只读；disconnect 仅 logout/必要 shutdown。
- [x] mock.py：确定性离线元数据；canvas.py：无网络 Protocol 与固定 Mock，不提供真实实现。
- [x] cli.py：默认 Mock，diagnose 无网络，qq 必须 --allow-real-mailbox；--detail 才显示主题并提示隐私。固定 JSON 输出与安全退出码。
- [x] 完整 pytest、CLI 冒烟与 wheel 构建/入口验证；文档记录结果后暂停。

重点：构造/导入/help/diagnose/pytest 不联网，不加载 Mock 的本机凭证。凭证与原始服务器错误不输出；不提供写、正文、附件能力。不执行真实邮箱测试。

当前目录最初因 Windows ACL 不可写；用户授予当前用户修改权限后已验证恢复。执行方式：本会话直接实现；没有创建 Git 仓库或提交。

后续状态（2026-10-12）：用户明确授权本机配置及真实 QQ 连接，已完成最近 3 封邮件头的只读验收与断开连接。此前“真实连接不在授权范围”的描述仅对应最初开发阶段；最新授权与证据见 phase1_validation.md。
