# AI 使用说明与记录

## 1. 文档目的

本文件说明本项目如何使用 AI，以及如何验证 AI 的输出。它既是开发规范，也是现场面试时解释 Vibe Coding 过程的证据。

原则：AI 可以帮助理解、设计、编码和草拟内容，但 AI 输出不能直接被视为正确结果。所有关键结果都需要通过运行、测试、数据校验或人工检查确认。

## 2. AI 在项目中的使用范围

AI 可以协助：

- 拆解 Homework 要求和设计实施顺序；
- 生成代码草稿、测试草稿和文档草稿；
- 动态发现评论主题；
- 归纳 Evidence Finding 和冲突观点；
- 草拟版本规划、PRD 和测试用例；
- 分析错误日志并提出修复方案；
- 检查 README、Demo 流程和面试表达。

AI 不得直接决定或伪造：

- 评论来源和评论正文；
- 评论数量、比例、评分分布；
- 不存在的 Review/Finding/Requirement/Test Case ID；
- 没有证据支持的“普遍问题”；
- 未运行测试却声称已经通过；
- 未真实执行的 Git 提交、推送或部署状态。

## 3. AI 与代码的职责分工

| 工作 | AI/模型 | Python/人工校验 |
|---|---|---|
| 主题发现 | 根据当前评论生成候选主题 | 检查结构、重复主题和样本覆盖 |
| 评论分类 | 判断评论属于哪些动态主题 | 保留 OTHER，统计数量 |
| Finding | 草拟标题、说明和证据 ID | 验证 ID、计算数量、调整置信度 |
| 版本规划 | 草拟版本目标、需求范围和验收标准 | Python 计算优先级并检查证据、覆盖与版本分配 |
| PRD | 草拟需求、范围和验收标准 | 检查来源、边界和可测试性 |
| 测试用例 | 草拟步骤和预期结果 | 检查 Requirement 与 Review 引用 |
| 数据统计 | 不负责 | 全部由 Python 计算 |
| 最终提交 | 提出提交范围和信息 | 测试通过、检查 diff 后执行 |

## 4. 防止 AI 幻觉的规则

每次调用模型时必须尽量满足：

1. 只允许根据输入评论分析。
2. 输入中包含稳定的 `review_id`。
3. 输出使用 Pydantic 或 JSON Schema。
4. 模型只能返回引用 ID，数量由 Python 计算。
5. Python 检查所有引用 ID 是否存在。
6. 非法引用不得进入下游 PRD 和测试用例。
7. 数据不足时使用“证据不足”或“产品假设”，不得夸大。
8. 展示冲突证据和数据限制。
9. 模型失败时保留已完成阶段，不伪造后续结果。

## 5. 推荐的 AI 开发工作方式

每次向 Codex 提任务时，尽量使用下面的格式：

```text
请先阅读 AGENTS.md、AI_USAGE.md 和 DEVELOPMENT_LOG.md。

本次目标：
只完成 [一个明确功能]。

验收标准：
1. ...
2. ...
3. ...

要求：
- 先检查当前代码和测试；
- 不覆盖无关修改；
- 完成后运行测试；
- 更新 DEVELOPMENT_LOG.md；
- 如果形成一个完整阶段，创建一个清晰的 Git commit；
- 不要推送，除非我明确要求。
```

示例：

```text
请完成动态主题发现的第一版。
只处理示例数据，不做 App Store 实时采集。
主题必须根据评论动态产生，不能写死健身 App 分类。
模型结果使用结构化输出；失败时显示清晰错误。
完成后添加测试、更新日志并提交，不要推送。
```

## 6. 每次 AI 参与后的记录模板

复制一条记录并填写：

```markdown
### YYYY-MM-DD / 任务名称

- 使用工具或模型：
- 我的目标：
- 提供给 AI 的关键信息：
- AI 生成或建议了什么：
- 我发现的问题：
- 我如何验证：
- 我做出的修改或取舍：
- 测试结果：
- 关联 commit：
```

## 7. 当前 AI 使用记录

### 2026-07-17 / 需求理解与实施路线

- 使用工具或模型：Codex。
- 我的目标：理解 LAIEN Homework，并制定适合零基础的实施顺序。
- 提供给 AI 的关键信息：官方题目、提交时间、个人当前基础。
- AI 生成或建议了什么：证据驱动的 Review → Finding → Requirement → Test Case 流程；先样例数据、后实时采集的开发顺序。
- 我发现的问题：初期方案包含较多专业词，不适合直接执行。
- 我如何验证：重新对照官方 README，并将方案改成零基础分阶段流程。
- 我做出的修改或取舍：选择 Python + Streamlit；暂不使用多 Agent、向量数据库和复杂前后端。
- 测试结果：不涉及代码测试。
- 关联 commit：首次项目基线提交。

### 2026-07-17 / 第一版可运行页面

- 使用工具或模型：Codex 辅助生成和解释代码。
- 我的目标：先跑通示例评论读取、CSV/JSON 上传、清洗和展示。
- AI 生成或建议了什么：`app.py`、示例数据、启动脚本和基础测试。
- 我发现的问题：当前版本尚未接入 AI，也没有 PRD、测试用例和追溯矩阵。
- 我如何验证：`app.py` 已通过 `py_compile`；3 个示例数据单元测试通过。
- 我做出的修改或取舍：保留最小可运行版本，下一阶段再增加动态主题。
- 测试结果：`python -m unittest discover -s tests -v`，3 tests passed。
- 关联 commit：首次项目基线提交。

### 2026-07-18 / 可审计的评论清洗过程

- 使用工具或模型：Codex 辅助设计清洗报告、UI 说明和测试案例。
- 我的目标：让面试官看见评论从原始数据到有效数据的具体处理过程。
- 提供给 AI 的关键信息：现有清洗代码、示例评论、确定性代码负责统计的项目原则。
- AI 生成或建议了什么：独立清洗模块、逐规则移除数量、数据保留率和“清洗过程”页面。
- 我发现的问题：旧实现会把 `2.5` 评分强制转换为 `2`，并且只能展示总移除数量，无法说明删除原因。
- 我如何验证：增加非法评分、空正文、重复 ID 和重复正文测试，并对示例数据的 6→5 结果进行断言。
- 我做出的修改或取舍：清洗保持纯 Python、固定顺序且不调用大模型；每条记录只计入首个失败原因。
- 测试结果：6 个单元测试通过，入口和清洗模块语法检查通过。
- 关联 commit：本次评论清洗说明提交。

### 2026-07-18 / 可追溯数据模型

- 使用工具或模型：Codex 辅助设计 Pydantic Schema 和验证用例。
- 我的目标：为后续模型输出规定稳定结构，使评论、主题、问题、需求和测试用例可以通过 ID 连接。
- 提供给 AI 的关键信息：题目要求的 Review → Topic → Finding → Requirement → TestCase 链路和美国区数据限制。
- AI 生成或建议了什么：五类核心模型、ID 前缀规则、必填证据字段、支持/冲突证据互斥校验。
- 我发现的问题：仅规定 JSON 字段不能保证引用合理，还必须禁止空证据、重复引用和错误 ID 类型。
- 我如何验证：构造一条完整追溯链，并使用非法评分、非美国区、空证据、错误前缀和冲突证据测试失败路径。
- 我做出的修改或取舍：当前阶段只验证数据结构；引用的 ID 是否真实存在，留到确定性追溯校验阶段处理。
- 测试结果：14 个测试通过；所有示例评论都能通过 Review Schema，Streamlit 默认页面无运行异常。
- 关联 commit：本次可追溯数据模型提交。

### 2026-07-18 / 分阶段参考案例手册

- 使用工具或模型：Codex 辅助整理案例与项目阶段的对应关系。
- 我的目标：避免盲目浏览或照抄，在做到某个阶段时查看相应优秀案例再继续开发。
- 提供给 AI 的关键信息：App Store Scraper、Apple Pipeline、LLM、Instructor + Pydantic、Python Validator、Streamlit 和 Rereflect 的职责划分。
- AI 生成或建议了什么：参考手册、阶段路由、借鉴记录模板和截止时间保护规则。
- 我发现的问题：参考项目功能很多，如果没有范围控制，容易偏离 Homework P0 闭环。
- 我如何验证：将每个案例映射到明确阶段，并要求记录“采用、不采用、原因和测试”。
- 我做出的修改或取舍：每阶段最多重点查看 1～2 个案例，不复制完整架构。
- 测试结果：文档链接、UTF-8 和现有 14 个自动测试通过后提交。
- 关联 commit：本次参考手册提交。

### 2026-07-18 / 阶段 2 动态主题发现

- 使用工具或模型：Codex；开发参考 Apple Review Summarization Pipeline、Instructor + Pydantic 和 OpenAI 官方模型文档。
- 我的目标：让系统根据当前评论提取原子观点并动态生成主题，不依赖写死行业分类。
- 提供给 AI 的关键信息：清洗后的 Review、用户分析目标、Topic Schema、OTHER 和失败停止要求。
- AI 生成或建议了什么：OpenAI-compatible 配置、Instructor 结构化输出、AtomicInsight / TopicDiscoveryResult、引用校验和 Streamlit 主题页。
- 我发现的问题：最初自动测试没有真正加载 Instructor；在 Python 3.9 下，当前 Instructor 还需要 `eval-type-backport` 才能创建客户端。
- 我如何验证：增加客户端创建、Prompt、内部 ID、非法 Review ID、评论遗漏和有效结果测试；手动点击未配置 Key 的分析按钮验证安全停止。
- 我做出的修改或取舍：借鉴 Apple 的 Atomic Insight 和无固定 taxonomy；当前轻量版在一次结构化调用中完成提取与聚合，不借鉴其微调模型、Embedding、模型训练和多模块云架构。
- 测试结果：22 个自动测试通过；入口及新增模块语法检查通过；缺少配置时 UI 清楚报错且不生成下游结果。
- 关联 commit：本次阶段 2 动态主题发现提交。

### 2026-07-18 / DeepSeek 结构化输出兼容修复

- 使用工具或模型：Codex、DeepSeek V4 Flash、Instructor、Pydantic。
- 我的目标：修复真实 DeepSeek 调用失败，并让页面显示可诊断但不泄密的底层错误。
- 提供给 AI 的关键信息：页面只显示 `InstructorRetryException`、DeepSeek 账户仍有余额、本地 `.env` 已配置。
- AI 生成或建议了什么：先验证认证与模型列表，再用单次最小请求提取异常链；针对 DeepSeek 结构化请求关闭 thinking；增加错误解包与脱敏。
- 我发现的问题：失败与余额无关。DeepSeek V4 默认 thinking，而 Instructor 强制 `tool_choice`，服务商返回 `Thinking mode does not support this tool_choice`；原 UI 把真实原因包装掉了。
- 我如何验证：模型列表接口确认 Key 和模型有效；26 个自动测试通过；真实 DeepSeek 调用对 5 条有效评论生成 5 个 Insight 和 4 个 Topic，所有引用校验通过。
- 我做出的修改或取舍：仅对 DeepSeek 添加 `thinking=disabled`，不影响其他服务商；页面展示最底层错误，但隐藏 API Key 和 Bearer Token；不保存这次示例结果为真实用户缓存。
- 测试结果：26 个自动测试通过；Python 语法检查通过；一次真实 DeepSeek V4 Flash 分析通过。
- 关联 commit：本次 DeepSeek 结构化输出兼容修复提交。

### 2026-07-18 / Atomic Insight 基数纠正与跨领域验收

- 使用工具或模型：Codex、DeepSeek V4 Flash、Instructor、Pydantic、Python Validator。
- 我的目标：澄清 Review 与 Atomic Insight 的正确关系，并完成第二领域动态主题验收。
- 提供给 AI 的关键信息：外卖测试页面显示 8 条有效评论、9 个 Insight、5 个 Topic，引用 ID 来自当前 CSV。
- AI 生成或建议了什么：AI 最初错误建议“一条 Review 最多一个 Insight”；用户指出与多观点评论设计矛盾后，改为 Review 1 → Insight 0..N、Insight 1 → Topic 1，并分别展示观点数与去重评论数。
- 我发现的问题：“每条 Insight 是原子的”不等于“每条 Review 只能产生一个 Insight”。8 条评论生成 9 条或更多 Insight 可能完全合理；真正需要阻止的是同一 Insight 跨 Topic 重复归类和无依据重复改写。
- 我如何验证：增加同一 Review 允许多个不同 Insight、同一 Insight 禁止跨 Topic 的测试；运行全部 29 个测试；对本地外卖 `synthetic_test` CSV 进行真实 DeepSeek 调用。
- 我做出的修改或取舍：保留多问题评论的独立观点；Topic 和 Finding 的评论数量必须按 Review ID 去重；跨 Topic 唯一性由 Pydantic 和最终 Validator 共同保证；测试 CSV 不作为真实用户证据。
- 测试结果：29 个自动测试通过；真实结果为 8 条评论、10 个 Insight、8 条去重证据 Review、0 OTHER、5 个动态 Topic，覆盖完整且无 Insight 跨 Topic 重复。
- 关联 commit：本次 Atomic Insight 基数纠正提交。

### 2026-07-18 / 阶段 3 Evidence Finding

- 使用工具或模型：Codex 辅助实现；DeepSeek V4 Flash 真实运行；参考 Apple Review Summarization Pipeline 的代表性证据、平衡观点和 Groundedness。
- 我的目标：把 Topic 转换为有支持评论、冲突评论、置信度和限制的问题，同时阻止单条评论被夸大。
- 提供给 AI 的关键信息：已验证 Review、Atomic Insight、Topic、分析目标和“不生成 PRD”的阶段边界。
- AI 生成或建议了什么：Finding Candidate、Discovery Candidate、Insight 级证据引用、Python 质量门和 Streamlit Evidence Finding 页面。
- 我发现的问题：第一次真实运行时，模型正确找到 `REV-005` 的订阅正面冲突观点，但手填的 `source_topic_ids` 没有包含承载该 Insight 的 Topic，质量门因此拦截。
- 我如何验证：把候选证据改为引用具体 Insight，由 Python 推导 Review 与 Topic；测试非法 Insight、错误情绪、Topic 遗漏、样本降级和置信度计算，再进行真实模型重跑。
- 我做出的修改或取舍：模型负责语义判断；Python 负责关系推导、去重数量、置信度和最小证据门槛。当前门槛为 2，只用于保守小样本演示，不宣称统计显著性。
- 测试结果：37 个自动测试通过；真实运行 4 个 Topic 得到 1 个 Finding 和 3 个 Discovery；主 Finding 有 2 条支持、1 条冲突，置信度由 Python 计算为 medium。
- 关联 commit：本次 Evidence Finding 提交。

### 2026-07-18 / Finding Groundedness 质量仪表盘

- 使用工具或模型：Codex 辅助设计和实现；运行时不调用大模型。
- 我的目标：让面试官一眼看到 Finding 的证据覆盖、引用完整性、无依据结论和冲突证据数量。
- AI 生成或建议了什么：FindingQualityReport、四项确定性指标、质量门状态和 UI 指标说明。
- 我发现的问题：直接给一个“Groundedness 87 分”缺少可解释的权重，也可能让模型质量看起来比实际更精确。
- 我如何验证：分别构造完整覆盖、遗漏 Discovery 和非法 Finding，验证覆盖率下降、追溯率下降与 Unsupported Claims 增加。
- 我做出的修改或取舍：不生成不透明总分；保留四个可复算维度，并在页面展示分子、分母和 Python 计算声明。
- 测试结果：Finding 专项 11 个测试通过；全部 40 个自动测试、入口语法和依赖检查通过。
- 关联 commit：本次 Finding Groundedness 质量仪表盘提交。

### 2026-07-18 / 阶段 4 版本规划与 PRD

- 使用工具或模型：Codex 辅助实现；DeepSeek V4 Flash 真实结构化调用；参考 Apple Pipeline 与 Python Validator 原则。
- 我的目标：把已验证 Finding 转成小而可执行的版本计划与 PRD，同时阻止 Discovery 或无证据想法成为承诺需求。
- 提供给 AI 的关键信息：Evidence Finding、支持与冲突证据、Groundedness 指标、分析目标和 Discovery 排除清单。
- AI 生成或建议了什么：Requirement Candidate、Release Candidate、暂缓 Finding、Product Hypothesis、范围、范围外事项和验收标准草稿。
- 我发现的问题：固定要求 3～6 条需求会鼓励小样本凑数；端到端真实重跑还遇到上游模型重复使用 Insight，系统按设计停止，没有伪造后续 PRD。
- 我如何验证：测试不存在 Finding、遗漏 Finding、同时处理和暂缓、重复版本分配、低置信度降级、Hypothesis 隔离和非法 Groundedness；再使用已通过质量门的固定 Finding 做真实模型调用。
- 我做出的修改或取舍：模型不能填写 Review ID、最终 REQ ID 和优先级；Python 从 Finding 派生两层来源关系，并按严重度和置信度计算 P0-P3。需求数量按证据实际需要为 1～6 条。
- 测试结果：新增 9 个阶段 4 测试；全部 49 个自动测试和语法检查通过；真实调用生成 1 个版本、1 条正式需求，完整处理 `FIND-001`。
- 关联 commit：本次阶段 4 提交。

### 2026-07-18 / Finding 重复 Insight 修复

- 使用工具或模型：Codex、DeepSeek V4 Flash、Instructor、Pydantic、Python Validator。
- 我的目标：修复模型把同一 Insight 同时放入 Finding 和 Discovery，导致结构化输出停止的问题。
- 提供给 AI 的关键信息：页面显示 `INSIGHT-005` 被多个 Finding/Discovery 重复使用，模型连接状态正常。
- AI 生成或建议了什么：保留现有唯一性质量门；在系统 Prompt 和靠近输出的用户消息末尾增加全局 Insight ID 自检、冲突证据覆盖说明和重叠候选合并规则；补充 Finding↔Discovery 重复测试。
- 我发现的问题：Schema 已禁止重复，但原 Prompt 没有明确表达；第一次只增加宽泛系统规则后，DeepSeek 两次仍把正面 `INSIGHT-005` 同时用作冲突证据和 Discovery。
- 我如何验证：增加针对性输出前检查；运行 Finding 专项 12 个测试和全部 50 个测试；真实执行 Review → Topic → Finding 链路。
- 我做出的修改或取舍：不删除质量门、不自动丢弃重复证据、不增加无限重试；冲突证据已算作 Topic 覆盖，不需要重复进入 Discovery。
- 测试结果：50 个自动测试通过；真实链路生成 1 个 Finding、3 个 Discovery，Evidence Coverage 100%、Review Traceability 100%、Unsupported Claims 0，质量门通过。
- 关联 commit：本次 Finding 重复 Insight 修复提交。

### 2026-07-18 / 阶段 5 测试用例与完整追溯检查

- 使用工具或模型：Codex 辅助实现；DeepSeek V4 Flash 真实结构化调用；Python Validator。
- 我的目标：从已验证 Requirement 生成可执行测试，同时证明每条测试可以回到真实评论。
- 提供给 AI 的关键信息：Requirement、验收标准、范围、范围外事项、优先级和来源评论原文。
- AI 生成或建议了什么：normal、negative、boundary 测试场景，以及前置条件、步骤和预期结果草稿。
- 我发现的问题：测试内容需要模型理解语义，但 TestCase ID、Review ID、优先级和覆盖率如果也交给模型，会与已验证 PRD 发生漂移。
- 我如何验证：测试未知 Requirement、P0/P1 场景缺失、P2 最小覆盖、上游证据不一致、篡改 Review、Prompt 约束和完整质量指标；再执行真实模型调用。
- 我做出的修改或取舍：模型只引用 Requirement；Python 派生最终 TestCase ID、来源 Review 和优先级，并要求 P0/P1 覆盖三类场景。
- 测试结果：新增 9 个阶段 5 测试；全部 59 个自动测试和语法检查通过；真实调用生成 3 条测试，场景与 Review 追溯覆盖均为 100%，Invalid References 为 0。
- 关联 commit：本次阶段 5 测试与追溯提交。

## 8. 面试时的解释模板

可以这样介绍：

> 我使用 AI 协助拆解需求、生成代码草稿和迭代 Prompt，但没有直接相信 AI 的结果。评论数量、评分分布、去重和引用关系由确定性代码完成；动态主题、问题归纳和需求草拟由模型完成。每个模型结论必须引用真实 Review ID，并通过程序校验后才能进入 PRD 和测试用例。开发过程中我记录了 AI 的建议、错误、验证方式和最终取舍。
