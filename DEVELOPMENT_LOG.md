# ReviewScope AI 开发日志与执行看板

## 1. 项目信息

- 项目：LAIEN App Review Insights Homework
- 当前目录：`E:\Codex\Projects\Study\app-review-insights`
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

## 3. 当前基线（2026-07-17 已验证）

已完成：

- [x] Streamlit 入口 `app.py`
- [x] 内置示例评论
- [x] CSV/JSON 上传入口
- [x] 必要字段检查
- [x] 评分转换、空评论过滤和基础去重
- [x] 逐规则清洗审计、移除原因和数据保留率
- [x] 原始数量、有效数量、移除数量和平均评分
- [x] 评分分布和清洗后评论表格
- [x] 本地启动说明及预览脚本

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

- 状态：已完成（两组测试数据真实模型验收通过）
- 阶段参考：Apple Review Summarization Pipeline、Instructor + Pydantic、所选 LLM 官方文档。
- 任务：
  - [x] 添加 `.env.example` 和模型客户端。
  - [x] 使用结构化输出生成动态 Topic。
  - [x] 禁止写死健身 App 分类。
  - [x] 支持 OTHER/无法判断。
  - [x] 模型失败时显示错误，不生成下游结果。
  - [x] 一条 Review 可生成多个独立 Insight，每条 Insight 只属于一个 Topic。
- 验收：更换评论数据后主题发生合理变化，结构校验通过。
- 已验证：29 个自动测试、Python 3.9 Instructor 客户端创建、未配置 Key 的 UI 失败停止路径；DeepSeek V4 Flash 对健身/订阅示例生成 5 个 Insight 和 4 个 Topic，对外卖 `synthetic_test` 的 8 条 Review 生成 10 个 Insight 和 5 个不同 Topic；覆盖 8 条去重 Review，无 Insight 跨 Topic 重复。
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
- 验收：不存在非法引用；每个 Finding 可展开真实评论。
- 已验证：40 个自动测试；内置演示数据真实生成 1 个 Finding 和 3 个 Discovery，支持、冲突和引用校验通过；Groundedness 指标使用确定性样例复算通过。
- 建议 commits：
  - `feat: generate evidence-grounded findings`
  - `fix: reject hallucinated review references`

### 阶段 4：版本规划与 PRD

- 状态：待开始
- 阶段参考：Apple Pipeline 的代表性证据与平衡原则、Python Validator。
- 任务：
  - [ ] 按证据、严重度、目标相关性和范围规划版本。
  - [ ] 生成 3–6 条核心 Requirement。
  - [ ] 每条包含来源、范围、不包含范围和验收标准。
  - [ ] 无证据建议标记为 Product Hypothesis。
- 验收：所有 Requirement 能追溯到 Finding 和 Review。
- 建议 commit：`feat: generate evidence-based release plan and PRD`

### 阶段 5：测试用例与追溯检查

- 状态：待开始
- 阶段参考：Python Validator。
- 任务：
  - [ ] 每个 P0/P1 Requirement 生成正常和异常测试用例。
  - [ ] 校验 TestCase → Requirement → Review。
  - [ ] 展示追溯矩阵和覆盖率。
- 验收：非法引用为 0；核心需求测试覆盖率为 100%。
- 建议 commit：`feat: add traceable test cases and quality gate`

### 阶段 6：美国区 App Store 采集

- 状态：待开始
- 阶段参考：App Store Scraper。
- 任务：
  - [ ] 解析 App Store URL 和 App ID。
  - [ ] 强制使用美国区评论。
  - [ ] 分页、限速、超时和有限重试。
  - [ ] 记录采集时间、来源和限制。
- 验收：题目链接可以获取真实评论；失败时保留上传和缓存路径。
- 建议 commit：`feat: add US App Store review collection`

### 阶段 7：缓存 Demo、导出和错误恢复

- 状态：待开始
- 阶段参考：Streamlit、Rereflect 信息层级。
- 任务：
  - [ ] 保存一次真实、经过校验的分析缓存。
  - [ ] 无 Key/无网络时一键加载缓存。
  - [ ] 导出 PRD Markdown、测试 CSV 和完整 JSON。
  - [ ] 保留已完成阶段，支持失败提示或单阶段重试。
- 验收：断网情况下仍能演示完整结果。
- 建议 commit：`feat: add offline demo exports and recovery`

### 阶段 8：最终交付

- 状态：待开始
- 阶段参考：Streamlit、Rereflect 信息层级。
- 任务：
  - [ ] README 补齐架构、数据来源、限制、防幻觉和启动命令。
  - [ ] 新目录、新虚拟环境重新安装和启动。
  - [ ] 检查 `.env`、Key、Cookie 和本地绝对路径。
  - [ ] 准备截图/GIF和 8 分钟 Demo。
  - [ ] 推送 GitHub，并在隐私窗口验证仓库可访问。
- 验收：提交检查表全部通过。
- 建议 commits：
  - `test: cover cleaning import and traceability`
  - `docs: add setup architecture and AI usage notes`

## 5. 当前唯一下一任务

> 进入阶段 4 版本规划与 PRD：只允许通过 Evidence 质量门的 Finding 进入需求，Discovery 不得伪装成确定性需求。

每条 Requirement 必须关联 Finding 和 Review，并包含范围、不包含范围与可测试验收标准。不得把 `.env`、Key 或未经真实运行产生的缓存结果提交到 GitHub。

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

- [ ] 新环境可以按照 README 启动。
- [ ] 使用美国区真实评论并说明限制。
- [ ] 展示采集、清洗、分类、分析、PRD 和测试中间过程。
- [ ] Requirement 可以追溯到 Review。
- [ ] Test Case 可以追溯到 Requirement 和 Review。
- [ ] 不存在非法 ID 和无证据的确定性结论。
- [ ] 无 API Key/无网络时缓存 Demo 可用。
- [ ] 测试全部通过。
- [ ] GitHub 不包含任何密钥或隐私信息。
- [ ] Git 提交历史真实清晰。
- [ ] 8 分钟 Demo 已至少彩排两次。
