# ReviewScope AI 开发日志与执行看板

## 1. 项目信息

- 项目：LAIEN App Review Insights Homework
- 项目位置：仓库根目录（不依赖本机绝对路径）
- 入口文件：`app.py`
- 推荐技术栈：Python + Streamlit + Pandas + Pydantic + OpenAI-compatible API
- 提交截止：2026-07-20 10:00（提交前应再次确认 HR 通知）


## 2. 使用规则

每次开始开发：

1. 阅读 `AGENTS.md`、`AI_USAGE.md`、`REFERENCE_PLAYBOOK.md` 和本文件。
2. 查看 Git 状态，不覆盖用户修改。
3. 运行当前测试和语法检查。
4. 查看当前阶段对应的 1～2 个参考案例，记录借鉴与不借鉴内容。
5. 只选择一个“下一任务”完成。

每次结束开发：

1. 运行测试。
2. 更新阶段状态和当天日志。
3. 记录错误、取舍和下一步。
4. 一个独立阶段通过验收后创建 Git commit。

参考学习必须服从 P0 范围和截止时间。完整映射、资料链接及记录模板见 `REFERENCE_PLAYBOOK.md`。

## 3. 初始基线（2026-07-17 已验证）

已完成：

- [x] Streamlit 入口 `app.py`
- [x] 内置示例评论
- [x] CSV/JSON 上传入口
- [x] 必要字段检查
- [x] 评分转换、空评论过滤和基础去重
- [x] 逐规则清洗审计、移除原因和数据保留率
- [x] 原始数量、有效数量、移除数量和平均评分
- [x] 评分分布和清洗后评论表格
- [x] 本地启动说明（早期静态预览已在最终交付前删除）

验证结果：

```text
app.py: py_compile passed
unittest: 3 tests passed
UTF-8 source read: passed
```

注意：PowerShell 默认读取曾显示中文乱码，但 Python 使用 UTF-8 读取正常。修改中文文件时必须保持 UTF-8。

## 4. 阶段看板

### 阶段 0：项目基线

- 状态：已完成
- 验收：页面可运行，示例评论可导入、清洗和展示。
- 下一步：进入阶段 1。

### 阶段 1：整理结构与数据模型

- 状态：已完成
- 任务：
  - [x] 将清洗逻辑拆到 `src/`，保持页面可运行。
  - [x] 定义 Review、Topic、Finding、Requirement、TestCase 数据模型。
  - [x] 增加 `source_id`、`storefront`、`source` 等来源字段。
  - [x] 为清洗和字段验证增加单元测试。
- 验收：所有对象具备稳定 ID，测试通过，页面功能无回退。
- 建议 commit：`feat: define traceable analysis schemas`

### 阶段 2：动态主题发现

- 状态：已完成（已升级为分批 Insight 提取 + 全量 Topic 聚合）
- 阶段参考：Apple Review Summarization Pipeline、Instructor + Pydantic、所选 LLM 官方文档。
- 任务：
  - [x] 添加 `.env.example` 和模型客户端。
  - [x] 使用结构化输出生成动态 Topic。
  - [x] 禁止写死健身 App 分类。
  - [x] 支持 OTHER/无法判断。
  - [x] 模型失败时显示错误，不生成下游结果。
  - [x] 一条 Review 可生成多个独立 Insight，每条 Insight 只属于一个 Topic。
  - [x] 按批次提取 Atomic Insight，再对全量 Insight 统一聚合 Topic。
  - [x] Python 分配全局 Insight/Topic ID并推导代表 Review。
- 验收：更换评论数据后主题发生合理变化，结构校验通过。
- 已验证：72 个自动测试；DeepSeek V4 Flash 将 5 条 Review 分 3 批提取 6 个全局 Insight，再统一形成 5 个 Topic；所有 Review 完整处理、Insight 恰好归入一个 Topic、代表 Review 全部由 Python 推导。
- 遗留限制：两组都是功能测试数据；最终用户结论仍必须使用阶段 6 采集的美国区真实评论或透明缓存。
- 建议 commit：`feat: add model-driven dynamic topic discovery`

### 阶段 3：Evidence Finding

- 状态：已完成（真实模型与质量门验收通过）
- 阶段参考：Apple Review Summarization Pipeline、Python Validator。
- 任务：
  - [x] 每个 Finding 返回支持和冲突 Review ID。
  - [x] Python 检查 Insight、Review 和 Topic 关系。
  - [x] Python 计算去重支持数量和置信度。
  - [x] 数据不足时降低置信度或放入 Discovery。
  - [x] 展示 Evidence Coverage、Review Traceability、Unsupported Claims 和 Conflict Evidence。
  - [x] 同一 Insight 不得跨 Finding/Discovery 重复使用。
- 验收：不存在非法引用；每个 Finding 可展开真实评论。
- 已验证：50 个自动测试；内置演示数据真实生成 1 个 Finding 和 3 个 Discovery，支持、冲突和引用校验通过；Evidence Coverage 与 Review Traceability 100%、Unsupported Claims 0；Groundedness 指标使用确定性样例复算通过。
- 建议 commits：
  - `feat: generate evidence-grounded findings`
  - `fix: reject hallucinated review references`

### 阶段 4：版本规划与 PRD

- 状态：已完成
- 阶段参考：Apple Pipeline 的代表性证据与平衡原则、Python Validator。
- 任务：
  - [x] 按证据、严重度、置信度和范围规划版本。
  - [x] 按证据实际需要生成 1–6 条核心 Requirement，不强行凑数。
  - [x] 每条包含来源、范围、不包含范围和验收标准。
  - [x] 无证据建议标记为 Product Hypothesis。
- 验收：所有 Requirement 能追溯到 Finding 和 Review。
- 已验证：49 个自动测试及相关语法检查通过；真实 DeepSeek 阶段 4 调用生成 1 个版本、1 条需求，Python 派生 `REQ-001`、`P1`、`FIND-001` 和两条来源 Review。
- 建议 commit：`feat: generate evidence-based release plan and PRD`

### 阶段 5：测试用例与追溯检查

- 状态：已完成
- 阶段参考：Python Validator。
- 任务：
  - [x] 每个 P0/P1 Requirement 生成正常、异常和边界测试用例。
  - [x] 校验 TestCase → Requirement → Finding → Review。
  - [x] 展示追溯矩阵、需求覆盖率、必需场景覆盖率和非法引用数。
- 验收：非法引用为 0；核心需求测试覆盖率为 100%。
- 已验证：59 个自动测试和语法检查通过；真实 DeepSeek 调用生成 3 条测试，normal/negative/boundary 全覆盖，Review Traceability 100%，Invalid References 0。
- 建议 commit：`feat: add traceable test cases and quality gate`

### 阶段 6：美国区 App Store 采集

- 状态：已完成
- 阶段参考：App Store Scraper。
- 任务：
  - [x] 解析 App Store URL 和 App ID。
  - [x] 强制使用美国区评论。
  - [x] 分页、限速、超时和有限重试。
  - [x] 记录采集时间、来源和限制。
- 验收：题目链接可以获取真实评论；失败时保留上传和缓存路径。
- 已验证：67 个自动测试和语法检查通过；使用题目中国区链接输入真实采集 100 条美国区评论，跨页 ID 唯一且 storefront/source 标记全部正确。
- 建议 commit：`feat: add US App Store review collection`

### 阶段 7：缓存 Demo 和错误恢复

- 状态：已完成（最终提交范围）
- 阶段参考：Streamlit、Rereflect 信息层级。
- 任务：
  - [x] 保存一次真实、经过校验的分析缓存。
  - [x] 无 Key/无网络时一键加载缓存。
  - [x] 保留已完成阶段，支持失败提示或单阶段重试。
- 验收：断网情况下仍能演示完整结果。
- 已验证：真实 50 条美国区评论完成 7 Topic、6 Finding、5 Requirement、15 TestCase；AppTest 从缓存恢复完整质量页面且不调用模型。
- 范围说明：结果导出属于可选增强项，未纳入本次提交；全部结构化结果与追溯关系均可在 UI 查看。
- 关联 commit：`00c60df feat: add verified demo cache and recovery`

### 阶段 8：最终交付

- 状态：已完成（包源网络限制已透明记录）
- 阶段参考：Streamlit、Rereflect 信息层级。
- 任务：
  - [x] README 补齐架构、数据来源、限制、防幻觉和启动命令。
  - [x] 新目录重新克隆并创建独立虚拟环境。
  - [x] 使用项目环境完成依赖检查、全量测试和 Streamlit 健康检查。
  - [x] 检查 `.env`、Key、Cookie 和本地绝对路径。
  - [ ] 准备截图/GIF和 8 分钟 Demo。
  - [x] 推送 GitHub，并核对远端提交。
- 验收：提交检查表全部通过。
- 建议 commits：
  - `test: cover cleaning import and traceability`
  - `docs: add setup architecture and AI usage notes`

## 5. 当前唯一下一任务

> 提交并推送最终交付文档；随后只保留现场 8 分钟 Demo 彩排。

缓存必须记录真实评论来源、采集时间、模型和限制；不得把本地测试数据或未完成结果伪装成真实缓存。不得把 `.env`、Key 或未经真实运行产生的缓存结果提交到 GitHub。

## 6. 每日开发记录

### 2026-07-17

- 完成：确认官方提交要求；生成零基础流程书；建立 AI 协作与日志规范。
- 当前可演示：示例数据、CSV/JSON 导入、清洗、统计和评论表格。
- 当前缺失：动态主题、Finding、PRD、测试用例、追溯矩阵、美国区采集、真实缓存。
- 验证：`app.py` 语法通过；3 个示例数据测试通过。
- 风险：父级 Git 仓库存在大量与本项目无关的未跟踪文件，提交时必须仅暂存 `app-review-insights/` 内相关文件。
- 下一步：阶段 1 数据模型与测试。

### 2026-07-18

- 完成：运行基线测试、语法检查和敏感信息扫描，准备将阶段 0 独立发布到 GitHub。
- 发布范围：仅包含 `app-review-insights` 独立仓库，不包含父目录的简历、输出文件或其他项目。
- 测试：3 个单元测试通过；`app.py` 与 `preview.py` 语法检查通过。
- 安全检查：未发现 API Key、GitHub Token 或密码；`.env` 和本地 secrets 已加入忽略规则。
- 当前限制：这仍然是阶段 0，不是最终 Homework；动态主题、Finding、PRD、测试用例追溯和真实评论采集尚未完成。
- 下一步：阶段 1 数据模型与测试。

### 2026-07-18 / 评论清洗过程说明

- 完成：将清洗逻辑拆到 `src/cleaning.py`，增加逐规则审计报告，并在 Streamlit 与零依赖预览页展示。
- 修改文件：`app.py`、`src/cleaning.py`、`tests/test_cleaning.py`、`preview.html`、`README.md`。
- 测试命令与结果：`python -m unittest discover -s tests -v`，6 个测试通过；3 个 Python 文件语法检查通过。
- 遇到的问题：旧逻辑只计算总移除数，并会将小数评分截断成整数。
- 我的取舍：清洗只使用确定性规则，不调用 AI；按照固定顺序记录首个移除原因。
- 当前可以演示：每一步清洗规则、移除数量、总移除数、保留率及规则原因。
- 尚未完成：动态主题、Finding、PRD、测试用例追溯与真实评论采集。
- 关联 commit：本次评论清洗说明提交。
- 下一步：阶段 1 数据模型与测试。

### 2026-07-18 / 阶段 1 可追溯数据模型

- 完成：定义 Review、Topic、Finding、Requirement、TestCase Pydantic 模型和引用结构。
- 修改文件：`src/schemas.py`、`tests/test_schemas.py`、`data/sample_reviews.json`、`requirements.txt`、`app.py`、`README.md`。
- 测试命令与结果：`python -m unittest discover -s tests -v`，14 个测试通过；Python 入口和模块语法检查通过；Streamlit 默认页面无运行异常。
- 遇到的问题：结构化输出只保证字段格式，不能证明引用 ID 在当前数据中真实存在。
- 我的取舍：本阶段验证字段、ID 类型和证据必填；跨对象真实存在性留到追溯校验阶段。
- 当前可以演示：示例评论来源字段；五类对象的稳定结构和失败验证。
- 尚未完成：动态主题、Finding、PRD、测试用例追溯与真实评论采集。
- 关联 commit：本次可追溯数据模型提交。
- 下一步：阶段 2 动态主题发现。

### 2026-07-18 / 项目参考与借鉴手册

- 完成：建立 `REFERENCE_PLAYBOOK.md`，将七类参考案例映射到各开发阶段。
- 修改文件：`REFERENCE_PLAYBOOK.md`、`AGENTS.md`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：文档链接和 UTF-8 检查通过；现有 14 个自动测试保持通过。
- 遇到的问题：参考案例覆盖面很大，全部照搬会超出截止时间和 P0 范围。
- 我的取舍：每阶段只重点查看 1～2 个案例，并记录采用、不采用、原因和验证。
- 当前可以演示：项目为什么参考这些案例，以及每个案例具体影响哪个阶段。
- 尚未完成：阶段 2 动态主题及后续完整闭环。
- 关联 commit：本次参考手册提交。
- 下一步：阶段 2 动态主题发现；开始前查看 Apple Pipeline、Instructor/Pydantic 和所选 LLM 文档。

### 2026-07-18 / 阶段 2 动态主题发现

- 完成：添加 OpenAI-compatible + Instructor 模型客户端、Atomic Insight、动态 Topic、OTHER、确定性引用校验和 Streamlit 展示。
- 修改文件：`.env.example`、`app.py`、`src/config.py`、`src/prompts.py`、`src/schemas.py`、`src/topic_discovery.py`、测试与项目文档。
- 测试命令与结果：`python -m unittest discover -s tests -v`，22 个测试通过；入口与新增模块语法检查通过；未配置 Key 时点击分析会明确停止。
- 遇到的问题：普通沙箱网络安装两次超时；允许联网后安装成功。Python 3.9 加载 Instructor 1.15.4 时缺少类型标注回退支持，增加 `eval-type-backport` 后客户端创建测试通过。
- AI 建议中的错误或风险：只验证 Schema 不等于真实客户端可运行；自动测试最初没有触发 Instructor 的延迟导入，后来补充了真实客户端创建测试。
- 我的取舍：由 AI 负责语义提取和动态聚合；由 Python 负责内部 ID、引用存在性、唯一归类、遗漏检查和失败阻断。
- 当前可以演示：模型配置状态、动态主题按钮、Atomic Insight、Topic 代表评论、OTHER、限制和清晰错误路径。
- 尚未完成：真实 Key 的跨数据集主题变化验收、Evidence Finding、PRD、测试用例、App Store 采集和真实缓存。
- 关联 commit：本次阶段 2 动态主题发现提交。
- 下一步：用自己的 Key 对两组不同数据做真实模型验收；通过后再进入阶段 3。
- 查看资料：Apple Review Summarization Pipeline、Instructor GitHub、Pydantic Schema 和 OpenAI 官方模型/结构化输出说明。
- 实际借鉴：原子 Insight、无固定 taxonomy、Pydantic 结构化输出、有限重试和错误停止。
- 明确不借鉴及原因：不采用 Apple 的模型微调、Embedding 去重、多模型训练和复杂云架构；这些超出本阶段 P0、截止时间和本地演示需要。

### 2026-07-18 / DeepSeek 结构化输出兼容修复

- 完成：定位并修复 DeepSeek V4 thinking 与 Instructor 强制 `tool_choice` 的冲突；页面展示脱敏后的底层服务商错误；模型状态区分“配置已读取”和“调用已验证”。
- 修改文件：`src/topic_discovery.py`、`app.py`、`tests/test_topic_discovery.py`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：主题发现专项 12 个测试通过；全部 26 个自动测试通过；`app.py`、`src/topic_discovery.py` 和 `src/config.py` 语法检查通过；真实 DeepSeek V4 Flash 调用成功。
- 遇到的问题：页面只显示外层 `InstructorRetryException`；底层错误是 `Thinking mode does not support this tool_choice`。原“模型配置：已就绪”也会让用户误以为 API 已经验证成功。
- AI 建议中的错误或风险：此前只根据 OpenAI-compatible 接口推断 Instructor 可直接工作，没有先验证 DeepSeek V4 默认 thinking 与强制工具选择的组合兼容性。
- 我的取舍：仅对 DeepSeek 结构化请求关闭 thinking，不降低其他模型能力；异常沿 cause 链提取，但必须替换 API Key、Bearer Token 并限制长度。
- 当前可以演示：DeepSeek 真实生成 Topic、成功状态、动态主题及引用；失败时可以看到可诊断且脱敏的服务商原因。
- 尚未完成：第二组不同领域评论的主题变化验收、Evidence Finding 及后续闭环。
- 关联 commit：本次 DeepSeek 结构化输出兼容修复提交。
- 下一步：上传第二领域 CSV，使用相同分析目标运行并对比 Topic。
- 查看资料：DeepSeek 官方 Thinking Mode 文档、Instructor + Pydantic 当前实现。
- 实际借鉴：显式控制 provider-specific thinking；保留 Pydantic 结构化输出、有限重试和确定性引用校验。
- 明确不借鉴及原因：不为 DeepSeek 单独重写整套客户端，不启用复杂 Agent 工具循环；当前任务只需要一次结构化分析调用。

### 2026-07-18 / Atomic Insight 基数纠正与跨领域验收

- 完成：纠正 Review 与 Atomic Insight 的基数关系；允许一条 Review 产生多个独立观点；保留 Insight 跨 Topic 唯一性；UI 分开展示观点数和去重评论数；完成第二领域真实模型验收。
- 修改文件：`app.py`、`src/prompts.py`、`src/schemas.py`、`tests/test_schemas.py`、`tests/test_topic_discovery.py`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：Schema 与 Topic 专项 22 个测试通过；全部 29 个自动测试通过；相关 Python 文件语法检查通过；外卖数据真实 DeepSeek 调用最终通过。
- 遇到的问题：截图显示 8 条评论生成 9 个 Insight；AI 最初误判为重复计数。用户指出一条评论可以包含多个观点后，确认这可能是正确的 Atomic Insight 拆分。真实重跑还发现同一 Insight 被分入两个 Topic，最终 Validator 正确拦截。
- AI 建议中的错误或风险：把“Insight 必须原子化”误解为“Review 只能产生一个 Insight”会丢失多问题评论证据；把 Insight 数量当作评论数则会夸大支持样本。
- 我的取舍：采用 Review 1 → Insight 0..N、Insight 1 → Topic 1；展示 Insight 数量与去重 Review 数量；将跨 Topic 唯一性放入 Pydantic 供 Instructor 有限修正，并保留最终 Validator。
- 当前可以演示：两组不同领域数据生成明显不同 Topic；8 条外卖 Review 生成 10 个有原文依据的 Insight，覆盖 8 条去重 Review，形成 5 个 Topic且无跨 Topic 重复。
- 尚未完成：Evidence Finding、PRD、测试用例、美国区真实评论采集和缓存 Demo。
- 关联 commit：本次 Atomic Insight 基数纠正提交。
- 下一步：阶段 3 Evidence Finding。
- 查看资料：Instructor + Pydantic 结构校验、项目 Python Validator 原则。
- 实际借鉴：Atomic Insight 原子化、多观点评论拆分、模型结构化阶段有限重试、确定性跨 Topic 唯一性和失败阻断。
- 明确不借鉴及原因：不强制一条 Review 只能一个 Insight，不增加无限重试，不让模型自行计算去重评论数；这些做法会丢失证据、掩盖错误或夸大统计。

### 2026-07-18 / 阶段 3 Evidence Finding

- 完成：增加 Finding/Discovery 候选 Schema、Insight 级证据引用、确定性质量门、置信度计算和 Streamlit Evidence Finding 标签页。
- 修改文件：`app.py`、`src/schemas.py`、`src/finding_prompts.py`、`src/finding_analysis.py`、`tests/test_finding_analysis.py`、README 与 AI/开发记录。
- 测试命令与结果：全部 37 个自动测试通过；相关 Python 文件语法检查通过；真实 DeepSeek 调用完成 Topic → Finding 链路。
- 遇到的问题：第一次真实 Finding 调用把一条有效正面冲突评论关联到了不完整的来源 Topic，严格质量门正确阻止了结果。
- AI 建议中的错误或风险：让模型同时填写 Insight、Review 和 Topic 三层关系会产生不一致；仅校验 Review ID 存在也无法证明它与问题语义相关。
- 我的取舍：模型只引用最细粒度 Insight；Python 从 Insight 推导 Review 与 Topic，并计算去重数量与置信度。少于 2 条支持评论自动进入 Discovery。
- 当前可以演示：Finding 数量、支持评论数、冲突评论数、严重度、置信度、原文下钻、限制和 Discovery 降级。
- 尚未完成：版本规划与 PRD、测试用例、美国区真实评论采集和缓存 Demo。
- 关联 commit：本次 Evidence Finding 提交。
- 下一步：阶段 4 版本规划与 PRD，只允许通过质量门的 Finding 进入需求。
- 查看资料：Apple Review Summarization Pipeline、项目 Python Validator 原则。
- 实际借鉴：代表性证据、平衡正反观点、Groundedness 和自动化质量检查。
- 明确不借鉴及原因：不采用模型微调、Embedding、多模型训练或人工评审平台；这些超出当前 P0 和截止时间范围。

### 2026-07-18 / Finding Groundedness 质量仪表盘

- 完成：增加 FindingQualityReport 与四项确定性 Groundedness 指标，并在 Evidence Finding 页展示质量门状态。
- 修改文件：`src/finding_analysis.py`、`app.py`、`tests/test_finding_analysis.py`、README 与 AI/开发记录。
- 测试命令与结果：Finding 专项 11 个测试通过；全部 40 个自动测试、入口语法和依赖检查通过。
- 遇到的问题：单一综合分需要人为设置权重，容易制造并不存在的精确性。
- AI 建议中的错误或风险：如果只显示百分比而不展示分子、分母，面试官无法判断 100% 来自 2 条还是 200 条评论。
- 我的取舍：展示四个独立可复算指标、覆盖分子/分母和质量门，不生成不透明综合分。
- 当前可以演示：Evidence Coverage、Review Traceability、Unsupported Claims、Conflict Evidence 和 Quality Gate 状态。
- 尚未完成：版本规划与 PRD、测试用例、美国区真实评论采集和缓存 Demo。
- 关联 commit：本次 Finding Groundedness 质量仪表盘提交。
- 下一步：阶段 4 版本规划与 PRD。
- 查看资料：项目 Python Validator 与确定性统计原则。
- 实际借鉴：代码复算、可解释分子/分母、非法引用计数和失败可见性。
- 明确不借鉴及原因：不让模型自评质量，不设置未经验证的综合权重；这些会降低可信度。

### 2026-07-18 / 阶段 4 版本规划与 PRD

- 完成：增加规划草稿 Schema、证据约束 Prompt、PRD 确定性质量门、版本路线图、需求详情、暂缓项、产品假设和 Finding → Requirement → Review 追溯矩阵。
- 修改文件：`app.py`、`src/schemas.py`、`src/planning_prompts.py`、`src/product_planning.py`、`tests/test_product_planning.py`、`tests/test_app.py`、README 与 AI/开发记录。
- 测试命令与结果：新增 9 个阶段 4 测试；全部 49 个自动测试及相关 Python 语法检查通过；真实 DeepSeek 阶段 4 调用通过。
- 遇到的问题：第一次端到端真实重跑时，上游 Finding 模型把相同 Insight 同时放入 Finding 和 Discovery，现有质量门正确阻断，因此改用一组通过同样质量门的固定 Finding 单独验证阶段 4。
- AI 建议中的错误或风险：固定要求 3～6 条需求会在小样本只有一个可靠 Finding 时诱导模型凑数；让模型填写 Review ID 和 P0-P3 会造成引用或统计幻觉。
- 我的取舍：需求数量改为证据驱动的 1～6 条；模型只引用 Finding，Python 派生 Review、最终 REQ ID、版本映射和优先级；全为低置信度时优先级保守降一级。
- 当前可以演示：版本目标、需求范围与范围外事项、验收标准、Finding 处理率、追溯矩阵、暂缓 Finding 和非承诺 Product Hypothesis。
- 尚未完成：测试用例、端到端追溯、美国区真实评论采集和缓存 Demo。
- 关联 commit：本次阶段 4 提交。
- 下一步：阶段 5 测试用例与完整追溯检查。
- 查看资料：Apple Review Summarization Pipeline 的代表性证据与平衡原则、项目 Python Validator 原则。
- 实际借鉴：证据驱动规划、明确范围边界、可测试验收标准、代码派生关系和失败停止。
- 明确不借鉴及原因：不采用固定需求数量、模型自评优先级、复杂 Agent 编排和无证据路线图；这些会制造填充内容或降低可解释性。

### 2026-07-18 / Finding 重复 Insight 修复

- 完成：让 Finding Prompt 与现有 Pydantic 唯一性规则对齐；明确每个 Insight 只能进入一个 Finding/Discovery，冲突证据已经算作 Topic 覆盖；增加输出前硬性自检。
- 修改文件：`src/finding_prompts.py`、`tests/test_finding_analysis.py`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：Finding 专项 12 个测试、阶段 3/4 联合 21 个测试和全部 50 个自动测试通过；相关 Python 语法检查通过；真实 Topic → Finding 链路通过。
- 遇到的问题：第一次只增加系统规则后，DeepSeek 在两次 Instructor 尝试中仍把 `INSIGHT-005` 同时作为冲突证据和 Discovery；将硬性自检放到用户消息末尾后真实运行通过。
- AI 建议中的错误或风险：仅依赖 Schema 事后报错会增加人工重试；自动删除重复 Insight 虽能让演示通过，却可能悄悄改变证据含义。
- 我的取舍：保留严格失败停止和一次有限重试；不删除校验、不自动修复模型证据、不增加无限重试；通过 Prompt 与 Schema 对齐降低失败率。
- 当前可以演示：1 个 Finding、3 个 Discovery、100% Evidence Coverage、100% Review Traceability、0 Unsupported Claims 和通过的质量门。
- 尚未完成：测试用例、端到端 TestCase 追溯、美国区真实评论采集和缓存 Demo。
- 关联 commit：本次 Finding 重复 Insight 修复提交。
- 下一步：阶段 5 测试用例与完整追溯检查。
- 查看资料：Instructor + Pydantic 结构校验、项目 Python Validator 原则。
- 实际借鉴：结构化输出约束、有限重试、输出前自检、确定性证据唯一性和失败阻断。
- 明确不借鉴及原因：不无限重试、不静默删除重复证据、不让模型自行声称质量门通过；这些会增加成本或降低可审计性。

### 2026-07-18 / 阶段 5 测试用例与完整追溯检查

- 完成：增加 TestCase Candidate Schema、测试 Prompt、确定性测试质量门、覆盖率报告、Streamlit 测试页和 Review → Finding → Requirement → TestCase 追溯矩阵。
- 修改文件：`app.py`、`src/schemas.py`、`src/test_prompts.py`、`src/test_generation.py`、`tests/test_test_generation.py`、`tests/test_app.py`、README 与 AI/开发记录。
- 测试命令与结果：新增 9 个阶段 5 测试；全部 59 个自动测试及相关 Python 语法检查通过；真实 DeepSeek 阶段 5 调用通过。
- 遇到的问题：模型适合草拟可执行步骤，但不应自行复制 Review、优先级或最终测试 ID，否则测试层可能和 PRD 层产生引用漂移。
- AI 建议中的错误或风险：只要求“每条需求有测试”可能让一个正常场景掩盖 P0/P1 的异常与边界缺口；把 out_of_scope 当成功能需求会扩大 PRD 范围。
- 我的取舍：P0/P1 强制 normal、negative、boundary 三类独立场景；P2/P3 至少 normal；Python 从 Requirement 派生 `TC-*`、Review 和优先级，并复算四项质量指标。
- 当前可以演示：测试详情、Requirement Coverage、Required Scenario Coverage、Review Traceability、Invalid References 和完整追溯矩阵。
- 尚未完成：美国区真实评论采集、缓存 Demo、导出和新环境最终验收。
- 关联 commit：本次阶段 5 测试与追溯提交。
- 下一步：阶段 6 美国区 App Store 评论采集与失败降级。
- 查看资料：项目 Python Validator 原则与现有 Pydantic/Instructor 结构化输出方式。
- 实际借鉴：模型草拟语义内容、代码派生引用、关键场景覆盖检查、可解释质量指标和失败阻断。
- 明确不借鉴及原因：不增加独立 Test Agent 编排、不让模型自报覆盖率、不生成无 Requirement 来源的探索性测试；这些会增加复杂度或削弱追溯性。

### 2026-07-18 / 阶段 6 美国区 App Store 评论采集与失败降级

- 完成：增加 App Store URL/App ID 解析、美国区 Lookup 验证、公开 RSS 有限分页采集、跨页去重、格式过滤、采集报告、Streamlit 实时数据源和 CSV/JSON 失败降级提示。
- 修改文件：`src/app_store.py`、`tests/test_app_store.py`、`app.py`、`tests/test_app.py`、README 与 AI/开发记录。
- 测试命令与结果：新增 8 个采集测试；全部 67 个自动测试及相关 Python 语法检查通过；题目 App 真实美国区采集通过。
- 遇到的问题：真实 Feed 的空页并不连续；题目 App 本次第 1～4、6 页为空，但第 5、7 页各返回评论。如果遇到首个空页就停止，会错误报告无数据。
- AI 建议中的错误或风险：直接抓 App Store 页面只能得到可见片段；依赖官方 App Store Connect API 又需要开发者授权，无法匿名读取指定第三方 App；无限翻页和重试会产生异常负载。
- 我的取舍：使用公开 iTunes Lookup/RSS 作为实时路径，最多 10 页、短间隔、每页一次有限重试；空页继续有限扫描，部分失败返回限制，完全无评论则停止并提示文件导入。
- 当前可以演示：输入中国区链接仍采集美国区、App 信息、100 条真实评论、采集时间、成功/空页、来源 URL、重复和格式异常统计。
- 尚未完成：真实缓存 Demo、导出、单阶段恢复和新环境最终验收。
- 关联 commit：本次美国区 App Store 采集提交。
- 下一步：阶段 7 缓存 Demo、导出和错误恢复。
- 查看资料：Homework 原始 README、Apple App Store Connect Customer Reviews 文档、项目 App Store Scraper 参考原则。
- 实际借鉴：按 storefront 分区、有限分页、请求间隔、稳定来源 ID、真实来源与限制可见、失败降级。
- 明确不借鉴及原因：不抓取页面 DOM、不复制第三方 scraper 代码、不使用无限重试、不把空页解释为零评论；这些做法脆弱、可能增加负载或产生错误结论。

### 2026-07-18 / 动态主题分批提取与统一聚合重构

- 完成：将单次 Review → Insight → Topic 调用拆成分批 Insight Extraction 与全量 Topic Aggregation；增加批次 Schema、全局 ID 分配、代表评论推导和逐层引用校验。
- 修改文件：`src/schemas.py`、`src/prompts.py`、`src/topic_discovery.py`、`tests/test_topic_discovery.py`、README 与 AI/开发记录。
- 测试命令与结果：Topic 专项 18 个测试、全部 72 个自动测试及语法检查通过；真实 DeepSeek 多批次调用通过。
- 遇到的问题：旧流程让一次模型调用同时读取全部评论、提取 Insight、生成三层 ID、聚合 Topic 和选择代表评论，输入扩大后职责过多且关系更容易漂移。
- AI 建议中的错误或风险：如果各批次自行生成 Insight ID，会产生跨批重复；如果各批次先生成 Topic，再合并 Topic，会失去全量语义对比；让模型选择代表评论还会增加一层可避免的引用幻觉。
- 我的取舍：每批模型只返回 Review 引用、观点和情绪；Python 按顺序生成全局 `INSIGHT-*`；第二次模型只聚合全量 Insight；Python 生成 `TOPIC-*` 并按 Topic 内 Insight 数量和原评论顺序选择最多 3 条代表 Review。
- 当前可以演示：多批次次数、全局唯一 Insight、统一 Topic、Python 代表评论和完整 Review/Insight/Topic 引用门。
- 尚未完成：阶段 6 提交尚未推送；真实缓存 Demo、导出和错误恢复仍待阶段 7。
- 关联 commit：本次动态主题两阶段重构提交。
- 下一步：先推送阶段 6 与本次修复，再进入阶段 7。
- 查看资料：项目 Apple Review Summarization Pipeline 与 Instructor/Pydantic 结构化输出原则。
- 实际借鉴：原子观点分批处理、聚合与提取职责分离、结构化输出、全局确定性 ID 和失败阻断。
- 明确不借鉴及原因：不做批次级 Topic 后合并、不用 Embedding/向量库、不让模型生成代表 Review；这些会增加语义漂移、复杂度或引用风险。

### 2026-07-18 / 动态主题遗漏的两级有限修复

- 完成：Python 对 Atomic Insight 批次的纯 Review 遗漏执行一次最小补提取；对 Topic 聚合的纯 Insight 遗漏执行一次最小分组修复；两者修复后都重新执行完整质量门。
- 修改文件：`src/schemas.py`、`src/prompts.py`、`src/topic_discovery.py`、`tests/test_topic_discovery.py`、`README.md`、`AI_USAGE.md`。
- 测试命令与结果：Topic 专项 27 个测试通过；全部 82 个自动测试、语法和依赖检查通过。
- 遇到的问题：100 条真实评论运行时，模型首轮漏掉 `REV-AS-14274175102`；此前只有聚合遗漏修复，提取层会直接停止。
- AI 建议中的错误或风险：重做完整批次或全量聚合会重复处理已正确结果；只看“存在遗漏”还可能掩盖非法 ID、重复归类或伪造 Review。
- 我的取舍：只有错误集合为纯遗漏时进入修复；只发送遗漏 Review/Insight；每一级最多一次，任何非纯遗漏或修复后错误仍立即停止。
- 当前可以演示：首轮遗漏单条评论时只补处理该评论并继续；若补提取仍遗漏，系统保持失败阻断。
- 关联 commit：本次动态主题两级有限修复提交。
- 下一步：用截图对应的 100 条美国区评论重新运行动态主题，确认页面展示有限补提取限制并继续 Finding。

### 2026-07-18 / 长页面快捷导航

- 完成：在固定侧边栏增加八个结果区域的快捷导航，并让选中项控制默认展示 Tab；增加右下角悬浮“回到顶部”入口。
- 修改文件：`app.py`、`tests/test_app.py`、`README.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：Streamlit 页面测试模拟直接切换到“测试用例与追溯”，页面无异常；完整回归见本次提交验证记录。
- 遇到的问题：原页面虽然已有顶部 Tab，但向下查看长结果后 Tab 会离开视野，返回其他阶段需要持续滚动。
- 我的取舍：保留现有 Tab 和分析状态，只增加固定导航与页内锚点，避免为了导航重写各阶段业务逻辑。
- 当前可以演示：从侧栏一键进入任一分析阶段，并可从长结果底部一键返回顶部。
- 下一步：启动浏览器进行一次完整 Demo 彩排，确认不同窗口尺寸下悬浮按钮不遮挡内容。

### 2026-07-18 / 测试候选数量动态收敛

- 完成：修复模型生成 31 条测试候选时被固定 30 条 Schema 上限提前拒绝的问题；Prompt 计算精确总数，Python 按 Requirement/场景组合确定性去重。
- 修改文件：`src/schemas.py`、`src/test_generation.py`、`src/test_prompts.py`、`tests/test_test_generation.py`、`README.md`、`AI_USAGE.md`。
- 测试命令与结果：31 条候选专项测试通过，Python 收敛为 3 条必需场景并记录移除 28 条；完整回归见本次提交验证记录。
- 遇到的问题：原 Prompt 使用“至少”措辞，模型会为一个场景生成多条变体；固定 `max_length=30` 又在 Python 质量门前直接中断。
- 我的取舍：原始候选安全上限提高到 60，仅用于接收有限冗余；最终有效数量仍由最多 6 条 Requirement 和优先级规则决定，不接受未知 Requirement，也不补造缺失场景。
- 当前可以演示：同类 31 条返回不会导致阶段失败，页面只展示覆盖完整且去重后的正式测试用例。
- 下一步：用截图对应的 100 条评论任务重新运行阶段 5，核对限制说明和追溯指标。

### 2026-07-18 / Finding 遗漏 Topic 有限补分析

- 完成：当 Finding 草稿的唯一问题是遗漏 Topic 时，只发送遗漏 Topic、其 Insight 与来源 Review 进行一次补分析；合并后重新执行完整质量门。
- 修改文件：`src/finding_prompts.py`、`src/finding_analysis.py`、`tests/test_finding_analysis.py`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：Finding 专项 16 个测试通过；完整回归见本次提交验证记录。
- 遇到的问题：100 条真实评论已通过 Topic 阶段，但 Finding 首轮遗漏 `TOPIC-009`、`TOPIC-013`，旧质量门只能停止，不能最小修复。
- AI 建议中的错误或风险：重新生成全部 Finding 可能改变正确证据分配；自动把遗漏 Topic 强行变成正式 Finding 会夸大弱证据。
- 我的取舍：补分析仍允许输出 Discovery；只引用遗漏 Topic 的 Insight；纯遗漏最多补一次，任何越界引用或二次遗漏继续停止。
- 当前可以演示：Finding 首轮遗漏少量 Topic 时最小补分析后继续；页面限制中记录补分析覆盖数量。
- 下一步：使用截图对应的 100 条评论再次生成 Evidence Finding，确认 `TOPIC-009`、`TOPIC-013` 被覆盖并通过 Groundedness Gate。

### 2026-07-18 / 阶段 7 真实缓存与单阶段恢复

- 完成：增加版本化 AnalysisSnapshot、真实 Demo 资格校验、原子写入、阶段成功自动检查点、同输入一键恢复、失败切换 Demo 和独立真实缓存生成脚本。
- 修改文件：`src/analysis_cache.py`、`scripts/build_demo_snapshot.py`、`app.py`、`tests/test_analysis_cache.py`、`tests/test_app.py`、`.gitignore`、README 与项目记录。
- 测试命令与结果：真实采集 50 条美国区评论，生成 7 Topic、6 Finding、5 Requirement、15 TestCase；缓存完整性校验通过；Streamlit AppTest 成功恢复 Finding/Test Quality 页面且没有模型调用。
- 遇到的问题：实时模型存在网络、结构化输出和完整覆盖的不确定性；只保存在 session_state 中，刷新或进程重启后无法恢复。
- AI 建议中的错误或风险：提交 `data/runtime` 会暴露个人运行状态；允许不完整或示例数据晋升为 Demo 会误导面试官；直接覆盖目标文件可能留下半份 JSON。
- 我的取舍：运行检查点 Git 忽略；公开 Demo 必须是真实美国区完整闭环；先写临时文件再原子替换；快照只记录模型名称，不保存 Key。
- 当前可以演示：无网络选择“真实缓存 Demo”直接查看完整链路；实时阶段失败后恢复同输入上次成功结果或切换缓存。
- 尚未完成：PRD Markdown、测试 CSV、完整 JSON 下载和新环境最终验收。
- 查看资料：Streamlit 状态管理与错误恢复原则、Rereflect 的结果信息层级。
- 实际借鉴：阶段状态可见、失败入口靠近错误、缓存结果可审计、先展示可靠结果再尝试实时运行。
- 明确不借鉴及原因：不引入数据库、登录、任务队列或云存储；Homework 本地演示不需要这些复杂度。

### 2026-07-18 / Finding 综合有限修复

- 完成：Python 同时识别证据角色错误候选和遗漏 Topic；删除错误候选后，只发送相关 Topic、Insight 与 Review 进行一次局部修复；合并时保留其他正确候选；最终重新运行完整 Finding 质量门。
- 修改文件：`src/finding_analysis.py`、`src/finding_prompts.py`、`tests/test_finding_analysis.py`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：Finding 专项 19 个测试、全部 94 个自动测试通过；Python 编译、依赖完整性与 Git 差异检查通过。
- 遇到的问题：100 条真实评论的首轮草稿中，`CAND-008` 把 `INSIGHT-0072` 错误作为 supporting，同时遗漏 `TOPIC-009/010/011/014`；旧逻辑只修复纯遗漏，因此按设计停止。
- AI 建议中的错误或风险：让 Python 按 sentiment 自动移动证据会把标签判断误当成语义冲突；重新生成全部 Finding 又可能破坏已经正确的候选。
- 我的取舍：模型只重判错误候选及遗漏范围；Python 确定允许使用的 Insight 集合、替换错误候选并执行最终质量门；伪造 Insight、非法 Review 和范围外引用仍直接阻断；最多修复一次。
- 当前可以演示：证据角色错误与 Topic 遗漏同时出现时，系统自动进行一次综合有限修复，通过后才允许进入 PRD。
- 关联 commit：`b649d82 feat: harden findings and unify dashboard UI`
- 下一步：在当前页面重新生成 Evidence Finding，确认100条真实评论触发综合修复后通过 Groundedness Gate。

### 2026-07-18 / Streamlit 双向导航与阶段页保持修复

- 完成：用可控的顶部横向导航替代不可编程切换的 Tabs；顶部与侧栏双向同步并只渲染当前结果页；四个阶段按钮触发整页重跑前会先保持对应阶段。
- 修改文件：`app.py`、`tests/test_app.py`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：App 专项 4 个测试、全部 96 个自动测试及 Python 编译检查通过。
- 遇到的问题：Streamlit Tab 的前端选择不会自动写入 Session State，`default` 也不能可靠控制已经存在的 Tabs；所以侧栏变化看似触发重跑，实际内容仍停在旧 Tab。
- 我的取舍：使用 Streamlit 原生 Radio、按钮回调和 Session State，不注入 JavaScript；用样式保持顶部 Tab 信息层级，并统一覆盖四个模型阶段。
- 当前可以演示：侧栏和顶部任一导航都能切换实际内容并同步另一侧；点击任一阶段生成按钮后，分析中和完成后保持当前结果页。
- 关联 commit：`b649d82 feat: harden findings and unify dashboard UI`

### 2026-07-18 / 评分柱状图关闭缩放

- 完成：数据概览改用固定 Altair 柱状图，未启用缩放或平移 Selection，并在局部容器隐藏图表工具栏；保留静态悬停数据提示。
- 修改文件：`app.py`、`requirements.txt`、`README.md`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：App 专项 4 个测试、全部 96 个自动测试、Python 编译和依赖检查通过。
- 遇到的问题：当前 Streamlit 1.50 的 `st.altair_chart` 使用 `use_container_width`，不是新版本的 `width` 参数；首次专项测试发现后已改为兼容写法。
- 我的取舍：复用 Streamlit 已依赖的 Altair，不额外引入 Plotly；工具栏样式只作用于评分图，避免影响其他组件。
- 当前可以演示：评分分布固定显示1至5星，不支持缩放、平移、框选或工具栏放大。
- 关联 commit：`b649d82 feat: harden findings and unify dashboard UI`

### 2026-07-18 / 黑白编辑风 UI 方向与全页面统一

- 完成：从参考图提炼字体、字号、留白、圆角、细描边和弱阴影规则；生成三套两页面方向稿并选择黑白编辑风；将设计令牌扩展到数据概览、清洗、评论、主题、Finding、PRD、测试和工作流程页面。
- 修改文件：`app.py`、`design/ui-directions/*`、`AI_USAGE.md`、`DEVELOPMENT_LOG.md`。
- 测试命令与结果：App 专项 4 个测试、全部 96 个自动测试和 Python 编译通过。
- 遇到的问题：字体 CSS 选择器范围过大导致 Streamlit Material 图标显示为 `keyboard_arrow_down`；Finding 的黑色严重度标签看起来像可点击选中态。
- AI 建议中的错误或风险：视觉稿中的强强调标签适合展示图，但直接套到真实交互页面会产生错误的可点击暗示；全页面重复采集报告也会让页面继续过长。
- 我的取舍：恢复 Streamlit 图标字体；静态标签全部改为浅灰，黑色只留给主操作；采集报告和基础数据只出现在概览页，复杂结果只默认展开第一项。
- 当前可以演示：同一套黑白设计语言覆盖完整 Review → Topic → Finding → Requirement → TestCase 页面，长页面可以通过双向导航快速切换。
- 关联 commit：`b649d82 feat: harden findings and unify dashboard UI`

### 2026-07-18 / 最终公开文档与启动验收

- 完成：删除只覆盖早期阶段的 `preview.html`、`preview.py` 和 `run-preview.bat`；README 改为最终提交口径；将公开开发看板、实际 commit 与提交范围同步到当前状态。
- 全新环境检查：从 GitHub 重新克隆仓库并成功创建 Python 3.9 独立虚拟环境；官方 PyPI 与清华镜像均出现包索引连接长时间等待，未在限定时间内完成全部第三方依赖下载。日志未将该结果伪装成安装成功，也没有观察到版本冲突、Python 不兼容或找不到版本错误。
- 最终功能验证：项目既有独立 `.venv` 执行 `pip check` 无损坏依赖；`app.py` 编译通过；96 项自动测试全部通过；Streamlit 实际启动后 `/_stcore/health` 返回 HTTP 200 和 `ok`。
- 取舍：不把某个第三方镜像写死到 README；仅建议升级 pip，并将包下载缓慢明确区分为外部网络问题。最终应用始终以 `app.py` 为唯一入口。
- 当前可以演示：美国区实时采集、真实缓存 Demo、动态 Topic、Evidence Finding、PRD、测试用例、全链路追溯、失败恢复和完整导航。
- 下一步：提交并推送本次最终文档收尾；现场面试前至少完成两次 8 分钟 Demo 彩排。

## 7. 每次收工填写模板

```markdown
### YYYY-MM-DD / 本次任务

- 完成：
- 修改文件：
- 测试命令与结果：
- 遇到的问题：
- AI 建议中的错误或风险：
- 我的取舍：
- 当前可以演示：
- 尚未完成：
- 关联 commit：
- 下一步：
- 查看资料：
- 实际借鉴：
- 明确不借鉴及原因：
```

## 8. 最终提交检查表

- [x] 全新仓库克隆与虚拟环境创建通过；依赖下载受当前包源网络限制，已透明记录。
- [x] 使用美国区真实评论并说明限制。
- [x] 展示采集、清洗、分类、分析、PRD 和测试中间过程。
- [x] Requirement 可以追溯到 Review。
- [x] Test Case 可以追溯到 Requirement 和 Review。
- [x] 不存在非法 ID 和无证据的确定性结论。
- [x] 无 API Key/无网络时缓存 Demo 可用。
- [x] 96 项测试、Python 编译、依赖检查和 Streamlit 健康检查通过。
- [x] GitHub 不包含任何密钥或隐私信息。
- [x] Git 提交历史真实清晰。
- [ ] 8 分钟 Demo 已至少彩排两次。
