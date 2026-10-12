# 开源项目复用评估

调研日期：2026-10-12（Asia/Shanghai）。范围：七个指定仓库的 GitHub 元数据、README、目录树，以及下文列出的许可证、依赖清单与关键代码。没有安装或执行仓库代码，没有提供任何邮箱凭证，没有调用邮箱或 Canvas API。

本报告是开发前评估；并非完整漏洞审计。最后 push 只证明最近存在提交，不能证明长期维护、测试质量或服务可靠性。依赖问题区分代码中可见的风险与尚未核验的漏洞；不将“未发现”称为“安全”。工作量为单人熟悉 Python 的工程估计，含适配和 Mock 测试，不含平台审核、学校审批和生产安全审计。

## 总体推荐

第一阶段直接复用 Python imaplib、email、ssl、pytest、Pydantic 和 python-dotenv 的成熟能力，独立实现小型 QQ 只读适配器。七个项目均不作为第一阶段运行依赖，也不复制其代码。这样既复用标准实现，又避免为 QQ 引入不适用的 OAuth、Node 服务和 MCP 写工具。

| 项目 | 技术栈 | 许可证 | 可复用模块或思路 | 集成难度 | 推荐决策 |
| -- | -- | -- | -- | -- | -- |
| [Agent Email MCP](https://github.com/UseJunior/email-agent-mcp) | TypeScript、Node 20+、googleapis、Azure Identity/MSAL、MCP | Apache-2.0 | OAuth 生命周期、按账号缓存、Graph 分页与 delta、错误净化、工具权限分层 | 高；Python 需服务桥接或重写 | 参考实现后自行开发 |
| [Gmail MCP Server](https://github.com/navbuildz/gmail-mcp-server) | TypeScript、Express、googleapis、MCP、可选 Upstash Redis | MIT | 多账号 TokenStore、metadata 读取、Token 更新边界 | 高；需移除写工具并重做授权安全边界 | 参考实现后自行开发 |
| [Canvas MCP](https://github.com/vishalsachdev/canvas-mcp) | Python 3.11+、httpx、Pydantic、FastMCP；可选 TypeScript code API | MIT | 数据模型、Link 分页、学生只读工具、公告/测验/日历归一化 | 中；完整服务偏重 | 参考实现后自行开发 |
| [Canvas Student Skill](https://github.com/Efan404/canvas-lms-student-skill) | Python、canvasapi、requests、Agent Skill 脚本 | MIT 文本附额外用途声明；API 为 NOASSERTION | 课程/作业查询、日历导出、Skill 工作流组织 | 低到中；许可证需先澄清 | 参考实现后自行开发 |
| [Cortex Study OS](https://github.com/PndaMan/cortex) | Rust/Tauri 2、Svelte 5、SQLite/sqlite-vec、可选本地模型与转录 | Apache-2.0 | 学业日历、资料来源定位、混合检索、卡片/模拟考试交互 | 高；桌面系统与 Python 核心不同 | 暂不采用 |
| [CanvasBuddy](https://github.com/philipnisevich/CanvasBuddy) | Next.js 15、React 19、TypeScript、Supabase、Anthropic | 未发现根 LICENSE；API license=null | Deadline/课程界面、来源呈现、工具调用交互 | 高；云数据库与外部模型 | 暂不采用 |
| [NotebookLM-Lite](https://github.com/LRriver/NotebookLM-Lite) | Python/FastAPI、前端 TypeScript、Docling、Chonkie、SeekDB、LiteLLM | Apache-2.0 | 文档摄取、带引用检索、结构化学习产物、长任务边界 | 高；重型文档与模型依赖 | 暂不采用 |

## 维护与取证快照

七个仓库均存在，GitHub 元数据均未标记 archived/disabled。下列日期为 API pushed_at（UTC）；tree SHA 固定本次目录快照，但关键文件通过 main 获取，不能保证跨请求完全原子一致。实际引入代码前应固定提交，再核验对应 LICENSE 和依赖锁文件。

| 仓库 | 最后 push（UTC） | tree SHA | 维护判断 |
| -- | -- | -- | -- |
| UseJunior/email-agent-mcp | 2026-10-07 06:44:37 | 379f97318f256c8427a6f9272791c00f982fcd32 | 近期活跃；年轻项目，不据此认定成熟 |
| navbuildz/gmail-mcp-server | 2026-10-02 22:17:28 | 82634ab6839c94b77ada35f5cd7b597c458302ff | 近期提交；需补 OAuth 安全验证 |
| vishalsachdev/canvas-mcp | 2026-10-12 01:55:41 | 7c4229c0ac05f10e5b09698ba824b17b82721beb | 近期活跃；有安全修复记录 |
| Efan404/canvas-lms-student-skill | 2026-04-04 19:42:53 | 040057c3042a7176fef7a2fbf50e2c8033881571 | 约半年无 push；持续维护未证实 |
| PndaMan/cortex | 2026-08-05 14:37:13 | 6d205c6b00f1a26660395a8789841aad462577ed | 约两个月无 push；长期维护未证实 |
| philipnisevich/CanvasBuddy | 2026-08-10 22:07:42 | d0bc85a6d21b8b46da3bd43c33092b6b81fa9e34 | 约两个月无 push；长期维护未证实 |
| LRriver/NotebookLM-Lite | 2026-07-10 07:21:27 | 0fb41d0d79267b29300ba31c12b8a5217cf416ad | 约三个月无 push；updated_at 较新不等于代码更新 |

元数据证据：[Agent Email](https://api.github.com/repos/UseJunior/email-agent-mcp)、[Gmail MCP](https://api.github.com/repos/navbuildz/gmail-mcp-server)、[Canvas MCP](https://api.github.com/repos/vishalsachdev/canvas-mcp)、[Student Skill](https://api.github.com/repos/Efan404/canvas-lms-student-skill)、[Cortex](https://api.github.com/repos/PndaMan/cortex)、[CanvasBuddy](https://api.github.com/repos/philipnisevich/CanvasBuddy)、[NotebookLM-Lite](https://api.github.com/repos/LRriver/NotebookLM-Lite)。

## 邮箱连接器（最高优先级）

### Agent Email MCP：参考实现后自行开发

检查 [Gmail auth.ts](https://github.com/UseJunior/email-agent-mcp/blob/main/packages/provider-gmail/src/auth.ts)、[Microsoft auth.ts](https://github.com/UseJunior/email-agent-mcp/blob/main/packages/provider-microsoft/src/auth.ts)、[Graph provider](https://github.com/UseJunior/email-agent-mcp/blob/main/packages/provider-microsoft/src/email-graph-provider.ts)、[package.json](https://github.com/UseJunior/email-agent-mcp/blob/main/package.json) 与 [LICENSE](https://github.com/UseJunior/email-agent-mcp/blob/main/LICENSE)。

Gmail 认证有自带 OAuth 客户端与 broker 两种路径，处理 access/refresh Token、到期和 401 后刷新。broker 模式会将 refresh token 发给 broker，不能用于本项目的默认配置。Microsoft 使用 MSAL/DeviceCodeCredential 与操作系统持久缓存，账号缓存名可隔离，Windows 使用 DPAPI。Graph 支持 nextLink、deltaLink 和删除 tombstone；分页结果落库成功后再提交最终游标，是本项目应自行落实的事务规则，不能因上游存在 delta 查询就认为已有完整同步恢复。

默认 full 权限包含读写和发送；observe 缩减工具表，却可能无法缩减此前同一应用已获的实际 Token 权限。未来要用独立应用注册、仅 Mail.Read 的授权、固定 GET 端点、工具白名单共同限制。不得接入 send、mark_read、move、标签、规则和附件写入工具。Graph 移动导致 ID 变化还需研究 ImmutableId；不能用 Message-ID 独自去重。

可以技术上拆出 provider/auth 包，但 Node 运行时、MCP、OAuth 缓存形成额外维护边界。Apache-2.0 一般允许商用与修改；复用需携带许可证、适用 NOTICE、版权并标记修改，注意专利条款，不获得商标权。第一阶段不复制；未来优先 Python 官方 OAuth SDK，自行写只读适配。

成本：桥接并审计裁剪约 4–7 人日；Python 单个 provider 元数据 OAuth/分页/Mock 约 3–5 人日，稳定增量与重授权另约 2–4 人日。需 Google/Entra 应用及可能管理员批准；本地方式无需额外托管，broker 则增加部署与信任成本。

### Gmail MCP Server：参考实现后自行开发

检查 [index.ts](https://github.com/navbuildz/gmail-mcp-server/blob/main/src/index.ts)、[gmail-service.ts](https://github.com/navbuildz/gmail-mcp-server/blob/main/src/gmail-service.ts)、[token-store.ts](https://github.com/navbuildz/gmail-mcp-server/blob/main/src/token-store.ts)、[package.json](https://github.com/navbuildz/gmail-mcp-server/blob/main/package.json) 与 [MIT LICENSE](https://github.com/navbuildz/gmail-mcp-server/blob/main/LICENSE)。

每账号保存 refresh token，获取 access token 后创建服务；TokenStore 使用 AES-256-GCM 与 scrypt，支持本地文件、环境恢复、Redis。但代码和 README 存在将加密账号数据以 TOKENS_DATA 输出供复制的路径；即使是密文，也不符合本项目不输出凭证材料的策略。MCP 密钥位于 URL，容易进入代理日志；OAuth state 使用管理员 key，未在所审阅路径看到独立一次性 state 验证，必须重做 CSRF/PKCE、回调绑定与重放防护。

配置请求 gmail.modify；服务包含发送、修改标签、草稿与退订。退订访问邮件指定链接并可能发信，不属于只读，还增加非可信 URL 的 SSRF 风险。listEmails 当前只获取一页并并行读 metadata，所审阅实现没有完整 nextPageToken/historyId 增量与事务恢复，不能直接用于长时间运行。

MIT 允许商用、修改和分发，保留版权与许可文本。可拆分 metadata 解析和账号隔离思路，但 TypeScript 无法直接导入 Python；不复用整服务或加密日志设计。未来仅 gmail.readonly、官方 Python SDK、本机安全 Token 存储。

成本：裁剪远程服务并修复安全/分页约 4–7 人日；Python 自行实现约 3–5 人日，加增量与失效恢复约 2–4 人日。需要 Google OAuth 应用；远程部署可能需要 HTTPS 和持久存储，本地不需要 Redis。

## Canvas 连接器

### Canvas MCP：参考实现后自行开发

检查 [pyproject.toml](https://github.com/vishalsachdev/canvas-mcp/blob/main/pyproject.toml)、[core/client.py](https://github.com/vishalsachdev/canvas-mcp/blob/main/src/canvas_mcp/core/client.py)、README 与 [LICENSE](https://github.com/vishalsachdev/canvas-mcp/blob/main/LICENSE)。Python 兼容性良好，但全服务引入 FastMCP/MCP/httpx 等；第一阶段无必要。README 披露已有写工具安全修复与公告，不等于所有风险已消除。需要固定经审计版本、锁定依赖、独立复核安全公告，不能将最新版依赖清单视为已验证可安装。

课程模型关注 id、course_code、name、time_zone；公告使用 discussion topic 类型，不能将所有讨论当公告；作业关注 due_at、unlock_at、lock_at、points_possible、submission_types 及个别截止时间覆盖；Quiz 与 New Quizzes 应保留类型，不能自动发起 attempt；日历关注 start_at、end_at、context_code、html_url。考试可能来自测验、公告或日历，不能仅凭名称推断确认时间。上述是接口设计字段，最终须对照官方 API 与学校许可校验。参考客户端 Link 分页、归一化、学生范围和隐私控制；Skill 用于流程配方，Tool 仅暴露受控读取动作。

MIT 可商用并保留通知。可将纯模型/解析/只读查询片段逐个评估，避免整体依赖、任意 TypeScript 执行、学生写工具。当前只预留 CanvasConnector 合约与 Mock，没有授权 Token，不访问真实 API，不模拟登录。

成本：全服务隔离裁剪 3–5 人日；轻量 Python 只读 2–4 人日，Mock 接口 0.5–1 人日。真实接入必须学校授权，可采用管理员批准的 OAuth/Token；禁止绕过学生 Token 限制。

### Canvas Student Skill：参考实现后自行开发

检查 [scripts/canvas_client.py](https://github.com/Efan404/canvas-lms-student-skill/blob/main/scripts/canvas_client.py)、[requirements.txt](https://github.com/Efan404/canvas-lms-student-skill/blob/main/requirements.txt)、目录与 [LICENSE](https://github.com/Efan404/canvas-lms-student-skill/blob/main/LICENSE)。canvasapi 提供分页抽象，脚本按课程/作业/日历任务组织，适合作为 Tool 与 Skill 分层参考。客户端从环境或用户目录明文 JSON 读 Token，初始化会验证真实用户，并可能直接输出上游异常，不符合本项目默认无网络和统一脱敏错误边界。其自生成 Token 指南不适用于理大当前限制。

许可证主体是 MIT，但末尾声明仅用于 educational/testing；GitHub 检测为 NOASSERTION。商业许可范围应向维护者澄清，澄清前不复制代码。宽范围依赖未证明可重复构建；不安装其脚本。

成本：脚本包装与安全替换 1–3 人日（许可澄清另计）；按官方协议自行实现 2–4 人日；Mock 0.5–1 人日。无独立服务必要，但真实连接仍需学校批准。

## 未来复习工作台（不属于本阶段）

### Cortex Study OS：暂不采用

检查 README、[package.json](https://github.com/PndaMan/cortex/blob/main/package.json)、Rust/前端目录及 [Apache LICENSE](https://github.com/PndaMan/cortex/blob/main/LICENSE)。可参考 Deadline 日历、课程资料分组、原始来源位置、SQLite 混合检索、FSRS 卡片、模拟考试与人工复核交互。PDF/PPT/文档处理、Whisper 转录与本地/云模型边界都应独立于邮箱核心。

Tauri/Rust/Svelte 与 Python 不兼容直接导入；需要 IPC/服务边界或重新实现。可选择本地模型，但部分功能使用外部模型/TTS、网络来源及侧车程序。文档解析、下载与侧车供应链均需额外审计。Apache-2.0 可商用，复用时遵循通知/修改/专利条款；目前不复制。

成本：整套接入与打包约 10–20 人日；后续独立做小型资料/RAG/日历工作台约 8–15 人日，不含语音与生成质量评估。桌面编译需 Rust/Node 与系统依赖；转录/模型可能需要本地算力或付费 API。

### CanvasBuddy：暂不采用

检查 README、[package.json](https://github.com/philipnisevich/CanvasBuddy/blob/main/package.json) 与根目录树。课程安排/作业上下文/Deadline 面板和带来源工具回答有产品参考价值；Next/React、Supabase 与 Anthropic 增加云端和个人数据边界。课程 Token、第三方模型发送、文档/ZIP/URL 工具需审计；未执行版本漏洞扫描，不能断言已存在或没有漏洞。

根目录未发现许可证，GitHub license=null。公开代码并不授予复制和商业使用权，只学习交互与架构，不复制组件或业务模块。成本：取得许可后全栈改造约 8–15 人日；独立开发简单只读事件界面约 3–6 人日。需 Node、云数据库/本地替代、可选模型费用和学校 OAuth 应用，当前暂不采用。

### NotebookLM-Lite：暂不采用

检查 README、[requirements.txt](https://github.com/LRriver/NotebookLM-Lite/blob/main/requirements.txt)、目录与 [Apache LICENSE](https://github.com/LRriver/NotebookLM-Lite/blob/main/LICENSE)。后续可评估 Docling 文档抽取、Chonkie 切片、SeekDB 混合检索、source/chunk 引用标识、笔记回流、结构化提纲/卡片/题目与异步任务状态。Python 可借鉴，但整体依赖包含 LangGraph、Docling、多个向量后端、LiteLLM/外部模型，违背第一阶段轻量范围。

文档上传、模型调用、文件导出和音频处理增加攻击面；requirements 使用大量下限约束，不能直接获得稳定锁定环境。未来优先逐项评估解析库，授权数据进入检索前保留页码/片段来源并限制外部发送。Apache-2.0 可商用且需通知/修改声明；当前不复制或安装。

成本：全服务隔离约 8–15 人日；小型 Python 文档与引用 RAG 约 5–10 人日，学习产物约 3–5 人日。需文档运行时、数据库，模型/嵌入/TTS 按部署选择另有算力或 API 成本。

## 最终架构与复用方案

1. 阶段一只有 QQ 元数据：config → CLI 显式授权门 → QQIMAPConnector → Pydantic 元数据 → 本地安全显示。构造、导入、help、diagnose 和 pytest 不建立真实连接；Mock 默认不读取本机凭证。
2. SSL 默认上下文强制校验主机与证书；QQ 固定 imap.qq.com:993，超时可配置。select(INBOX, readonly=True) 在 imaplib 中发 EXAMINE；UID SEARCH 解析、数值去重排序、取最新 10 个 UID；UID FETCH 只使用 BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)]。不读正文/附件，不使用 CLOSE（防止未来误切写模式后的风险），仅 logout/必要 shutdown。
3. 元数据 Date 保留时区；缺失、无时区或坏格式标记未知，不自行补时区。MIME 字符集错误安全退化；默认主题全部隐藏，detail 仅本地显式打开并提示隐私。服务器错误仅映射固定错误码/说明，禁止输出原始异常与凭证上下文。
4. Canvas 当前只有无网络接口约定与固定模拟模型验证。网易/Gmail/Graph、完整 MailMessage、分类/提取、SQLite、课程历史与七天摘要留在阶段二，按用户确认后实现，不提前扩大本阶段。
5. 未来 MailConnector 定义 connect/verify_connection/list_message_ids/fetch_message/sync_messages/disconnect；唯一键 provider + account_id + provider_message_id。IMAP UIDVALIDITY 纳入同步世代，重置时重新核对；Gmail history 失效受控重建；Graph 完整分页后事务提交 deltaLink。Message-ID 仅用于来源关联。重试仅限幂等读取并限制次数，错误入可重处理队列。
6. 未来 OAuth 优先官方 Python SDK；本机 OS 安全缓存、一次性 state/PKCE、账号隔离、只读 scope 与 GET 白名单。只有用户批准真实邮件/外部 AI 数据用途后才开放对应功能。

## 开发前状态与下一步

当前会话可写根均位于 C 盘；尝试创建 D:\academic-mail-agent 返回 Access denied。尚未在 D 盘创建项目。报告先保存在当前会话 outputs/docs，待开放 D 盘工作区后放入项目 docs/open_source_evaluation.md。

开发执行顺序：先本报告与架构 → 初始化工程及先失败的 Mock 测试 → 实现 QQ 连接器与 CLI → 执行 pytest、安全检查、打包验证 → 暂停等待用户批准真实邮箱测试。安全测试应覆盖禁止写入、PEEK、UID 兼容、MIME/日期错误、空箱、证书与网络失败、凭证净化、默认无网络和退出清理。真实邮箱连接尚未执行，测试通过数尚无结果。
