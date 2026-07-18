# ReviewScope AI

这是 App Review Insights Homework 的阶段 6 可运行版本，核心分析闭环和美国区实时数据入口已经打通。

当前版本已经可以：

- 加载内置示例评论；
- 上传 CSV 或 JSON 评论文件；
- 检查必要字段；
- 删除空评论、异常评分和重复评论；
- 展示每条清洗规则、移除数量、保留率和规则原因；
- 展示数据统计、评分分布和评论表格；
- 使用 AI 提取 Atomic Insight，并根据当前评论动态聚合 Topic；
- 支持 OTHER / 无法判断，使用 Python 拦截不存在、重复或遗漏的引用；
- 生成带支持证据、冲突证据、置信度和数据限制的 Evidence Finding；
- 把证据不足的问题降级到 Discovery，不让它进入正式产品规划；
- 生成版本路线图与 PRD，展示需求范围、范围外事项和验收标准；
- 由 Python 建立 `Finding → Requirement → Review` 追溯并计算需求优先级；
- 生成正常、异常和边界测试用例；
- 展示 `Review → Finding → Requirement → TestCase` 完整追溯矩阵和质量门。
- 输入任意地区 App Store 链接并强制采集美国区公开书面评论；
- 展示采集时间、来源 URL、分页结果、去重和失败限制。
- 使用固定侧栏快捷导航直接切换分析阶段，并提供悬浮“回到顶部”入口。

下一阶段将增加离线缓存 Demo、导出和单阶段错误恢复。

项目采用“参考案例驱动、确定性验证”的迭代方式。每个阶段开始前只查看对应案例，记录借鉴与不借鉴内容，再进行实现和测试。完整路线见 [项目参考与借鉴手册](REFERENCE_PLAYBOOK.md)。

## 立即预览（不需要安装依赖）

如果还没有安装 Streamlit，可以直接双击：

```text
run-preview.bat
```

或者运行：

```powershell
py preview.py
```

浏览器会打开零依赖预览页。这个预览页用于确认第一阶段的页面和数据流程；正式应用入口仍然是 `app.py`。

## 运行方法

先克隆仓库并进入项目：

```powershell
git clone https://github.com/Peiking0212/app-review-insights-homework.git app-review-insights
cd app-review-insights
```

创建虚拟环境：

```powershell
py -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

复制模型配置模板：

```powershell
Copy-Item .env.example .env
```

使用文本编辑器打开 `.env`，至少填写：

```text
OPENAI_API_KEY=你的模型密钥
OPENAI_MODEL=你实际可用的模型名称
```

使用 OpenAI 官方接口时 `OPENAI_BASE_URL` 可以留空；使用兼容接口时，填写服务商官方文档提供的地址。`.env` 已被 Git 忽略，不能把真实密钥提交到 GitHub。

使用 DeepSeek 官方接口时可以填写：

```text
OPENAI_API_KEY=你的 DeepSeek API Key
OPENAI_MODEL=deepseek-v4-flash
OPENAI_BASE_URL=https://api.deepseek.com
```

DeepSeek V4 默认开启 thinking，但 Instructor 的结构化输出会发送强制工具选择。项目检测到 DeepSeek 时会仅对结构化分析请求关闭 thinking，避免 `Thinking mode does not support this tool_choice`。这个兼容参数不会发送给 OpenAI 或其他模型服务。

启动网站：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

终端会显示一个本地地址，通常是：

```text
http://localhost:8501
```

用浏览器打开这个地址即可。

页面较长时，可以在左侧“页面快捷导航”直接选择动态主题、Evidence Finding、
版本规划与 PRD、测试用例与追溯等结果页。右下角的“↑ 回到顶部”按钮会始终可见，
无需手动滚动回页面最上方。

## 上传文件格式

CSV 或 JSON 至少需要这三个字段：

```text
review_id
rating
content
```

其他字段，例如 `title`、`version` 和 `published_at`，可以暂时缺少。

内置示例数据标记为 `illustrative_sample`，只用于验证页面和清洗流程，不能作为最终分析中的真实用户证据。最终演示必须替换为可说明来源的美国区真实评论或透明标记的缓存结果。

## 美国区 App Store 实时采集

侧栏选择“美国区 App Store 实时采集”，可以输入美国区、中国区或其他地区的 `apps.apple.com` 链接。系统只提取数字 App ID，然后使用美国区 Lookup 与公开 Customer Reviews RSS Feed，因此输入中国区链接也不会采集中国区评论。

```text
任意地区 App Store URL
→ 提取 App ID
→ 美国区 Lookup 验证 App
→ 有限扫描美国区公开评论 Feed（最多 10 页）
→ 过滤格式异常、跨页去重
→ 统一标记 storefront=us 和 source=apple_public_rss_us
→ 清洗与 AI 分析
```

采集器每次最多请求 500 条评论，页面之间保留短间隔，每页只进行一次有限重试。公开 Feed 可能出现非连续空页，因此不会因为第一页为空就停止；页面会显示尝试页数、成功页数、空页、实际数量、重复数、采集时间和请求 URL。

数据来源与限制：

- Apple 官方 App Store Connect API 支持获取 Customer Reviews，但需要开发者授权，适合读取自己管理的 App，不适合匿名读取 Homework 指定的第三方 App；
- 本项目实时路径使用 Apple 公开 iTunes RSS/Lookup 端点，不需要 API Key，但它不是稳定性承诺明确的完整历史归档；
- 最多扫描 10 页，通常最多约 500 条近期书面评论，不代表全部评分或全部历史用户；
- Feed 可能返回空页、重复、限流、网络错误或格式变化；部分页失败时透明返回部分数据和限制，完全没有可用评论时停止；
- 实时失败后切换到 CSV/JSON 导入。阶段 7 会增加经过验证的真实缓存，当前不会用内置示例冒充实时结果。

2026-07-18 真实验收使用题目的中国区链接输入，系统仍定位美国区 App ID `839285684`，有限扫描 7 页获得 100 条去重书面评论。所有记录均标记 `storefront=us`，来源均为 `apple_public_rss_us`；前 4 页及第 6 页为空，系统继续扫描并在后续页获得数据。该结果证明采集和失败透明路径可用，但数量会随 Apple 当前 Feed 变化。

## 评论清洗过程

清洗完全由确定性 Python 规则完成，不调用大模型，并按照固定顺序执行：

1. 删除 `review_id` 为空的记录；
2. 删除无法解析、超出 1～5 或不是整数的评分；
3. 删除正文为空的记录；
4. 对相同 `review_id` 去重；
5. 忽略大小写和多余空白，对相同正文去重。

每条评论只在首次命中的规则中计数。页面的“清洗过程”标签会展示每一步移除的数量、总移除数量和数据保留率。原始上传文件不会被覆盖。

## 可追溯数据模型

项目使用 Pydantic 定义五类核心对象：

```text
Review → Topic → Finding → Requirement → TestCase
```

- `Review` 保存内部 ID、来源 ID、美国区标记和原始评论内容；
- `Topic` 必须引用代表性 Review ID；
- `Finding` 必须引用 Topic 和支持评论，并区分冲突证据；
- `Requirement` 必须引用 Finding 和 Review，且包含范围与验收标准；
- `TestCase` 必须引用 Requirement 和 Review。

模型会拒绝缺少证据、ID 前缀错误、引用重复以及同一评论同时作为支持与冲突证据等结构问题。动态主题阶段还会用 Python 检查引用是否真实存在于本次数据集。

## 动态主题发现

阶段 2 的流程是：

```text
清洗后 Review
→ Python 按固定大小分批（默认每批 20 条）
→ AI 每批只提取 Atomic Insight Candidate
→ Python 校验每批 Review 覆盖并分配全局 INSIGHT-* ID
→ AI 对全部已验证 Insight 统一聚合 Topic Candidate
→ Python 分配 TOPIC-* ID并推导代表 Review
→ Python 校验 Review / Insight / Topic 全部引用
→ UI 展示主题、原子观点、代表评论和限制
```

Insight 提取和 Topic 聚合使用两个不同的 Schema 与 Prompt。提取批次看不到 Topic 字段，也不允许生成 Insight ID；聚合步骤只接收全量已验证 Insight，看不到原始评论，也不允许输出代表评论。这样避免单次请求同时承担长文本提取、跨评论聚合和三层 ID 关系。

提示词明确禁止预设健身、订阅、广告等行业分类。一条 Review 可以包含多个独立问题，因此可以生成多条 Atomic Insight；但每条 Insight 只能表达一个具体方面和一种主要情绪，并且只能归入一个 Topic。完全没有可用 Insight 的评论进入 `OTHER`。Pydantic 与最终 Python Validator 会共同拦截批次遗漏、跨批非法 Review、跨 Topic 重复归类、虚构 Insight 和未分配 Insight。如果任一批次、统一聚合或引用校验失败，本阶段会停止，不会继续生成没有证据的 Finding 或 PRD。

UI 会同时展示 Atomic Insight 数量和涉及的去重 Review 数量。后续统计“支持评论数”时必须按 Review ID 去重，不能把 Insight 数量当作用户评论数量。

侧栏的“模型配置：已读取”只代表 `.env` 字段齐全；只有真实模型请求成功后才会显示“模型调用：已验证”。调用失败时，页面会显示脱敏后的底层服务商错误，API Key 和 Bearer Token 会被隐藏。

内置数据只能验证这条流程。2026-07-18 重构后使用本地 DeepSeek Key，以 `batch_size=2` 将 5 条有效评论分为 3 批，生成 6 个由 Python 统一编号的 Atomic Insight，再全量聚合为 5 个由 Python 编号的 Topic。所有评论均被处理、所有 Insight 恰好归入一个 Topic、所有代表评论均来自 Topic 内 Review。此前外卖领域 `synthetic_test` 也证明 Topic 会随输入变化；这些仍是功能测试数据，不能替代最终美国区 App Store 真实评论。

## Evidence Finding

阶段 3 将 Topic 转换成可以审查证据的问题：

```text
Review → Atomic Insight → Topic
→ 模型草拟 Finding Candidate / Discovery Candidate
→ Python 从 Insight 推导 Review 与 Topic
→ 校验支持与冲突证据
→ Python 计算支持数量和置信度
→ Finding 或 Discovery
```

模型只引用具体 `INSIGHT-*`，不能自行填写 Review 数量、比例或置信度。Python 会从 Insight 关系确定来源 Topic 和去重 Review ID，并执行以下质量门：

- 支持证据必须来自 `negative` 或 `mixed` Insight；
- 冲突证据必须来自 `positive` 或 `mixed` Insight；
- 不存在的 Insight、Review、Topic 和遗漏 Topic 会阻止本阶段；
- 每个 Insight 在全部 Finding Candidate 与 Discovery Candidate 中最多引用一次；已作为冲突证据使用的 Insight 不得再次进入 Discovery；
- 同一 Review 不能同时作为同一个 Finding 的支持和冲突证据；
- 少于 2 条去重支持评论的候选进入 Discovery；
- 置信度根据支持数、冲突数和 Topic 覆盖计算，不接受模型估算。

`MIN_FINDING_SUPPORT = 2` 是当前小样本演示的保守门槛，不代表统计显著性。最终使用大规模美国区评论时应根据样本量重新校准。

2026-07-18 使用内置演示数据真实运行阶段 3：4 个 Topic 生成 1 个 Evidence Finding 和 3 个 Discovery。`FIND-001` 有 2 条去重支持评论、1 条冲突评论，Python 计算置信度为 `medium`；其余单评论问题均被降级，没有被描述为普遍问题。该结果只验证流程，不是最终产品结论。

同日真实端到端重跑曾发现模型把 `INSIGHT-005` 同时作为 Finding 冲突证据和 Discovery 线索，Pydantic 正确阻止下游。修复后 Prompt 在系统规则和输出前自检中都明确 Insight 全局唯一分配；再次真实运行生成 1 个 Finding 与 3 个 Discovery，Evidence Coverage 和 Review Traceability 均为 100%，Unsupported Claims 为 0，质量门通过。没有删除校验、自动丢弃证据或增加无限重试。

### Finding Quality · Groundedness Score

Evidence Finding 页面会显示四个由 Python 复算的质量指标，不额外调用模型：

| 指标 | 确定性定义 |
|---|---|
| Evidence Coverage | Finding 与 Discovery 引用的 Topic 去重评论数 ÷ Topic 阶段涉及的去重评论数 |
| Review Traceability | 当前数据集中真实存在的被引用评论数 ÷ 全部被引用评论数 |
| Unsupported Claims | 缺少有效支持、引用越界、证据情绪错误或来源 Topic 不成立的 Finding 数量 |
| Conflict Evidence | 所有 Finding 引用的去重冲突评论数量 |

页面同时显示分子和分母，例如“覆盖 8/9 条 Topic 去重评论”，避免只有百分比却无法解释。当前不把四个维度强行加权成一个不透明总分；质量门要求存在证据覆盖、`Review Traceability = 100%` 且 `Unsupported Claims = 0`。

## 版本规划与 PRD

阶段 4 只接收通过 Groundedness 质量门的 Evidence Finding：

```text
已验证 Finding
→ 模型草拟 Requirement Candidate、版本目标与验收标准
→ Python 校验 Finding 是否全部处理
→ Python 从 Finding 派生真实 Review ID
→ Python 根据严重度和置信度计算 P0-P3
→ 最终 Release Plan + Requirement + 追溯矩阵
```

模型不能自行填写最终 `REQ-*`、Review ID 或 P0-P3。Python 会确保每条候选需求恰好进入一个版本，每个 Finding 要么被需求覆盖、要么明确暂缓，不能遗漏或同时出现在两处。正式需求包含 `in_scope`、`out_of_scope` 和可观察的验收标准。

需求数量按证据实际需要生成 1～6 条，不强行凑成固定数量。Discovery 不能进入正式需求；没有当前评论证据的想法只能单独标记为 `Product Hypothesis`，并展示验证计划，不能伪装成版本承诺。

2026-07-18 已使用真实 DeepSeek 结构化调用单独验证阶段 4：一条通过质量门的订阅透明度 Finding 生成 1 个版本和 1 条正式需求。最终 `REQ-001`、`P1`、来源 `FIND-001` 以及 `REV-001/REV-002` 均由 Python 生成或派生。该数据只用于功能验证，不代表真实 App Store 用户结论。

## 测试用例与完整追溯

阶段 5 从已验证 Requirement 生成测试草稿：

```text
Requirement + Acceptance Criteria
→ 模型草拟 normal / negative / boundary 场景
→ Python 校验 Requirement ID 与场景覆盖
→ Python 派生 TC ID、优先级和 Review ID
→ Review → Finding → Requirement → TestCase 质量门
```

每条 Requirement 至少需要正常场景；P0/P1 必须同时覆盖正常、异常和边界场景。模型不能填写最终 `TC-*`、Review ID 或优先级。页面展示四个确定性指标：

| 指标 | 确定性定义 |
|---|---|
| Requirement Coverage | 至少拥有一条测试的需求数 ÷ 全部需求数 |
| Required Scenario Coverage | 已覆盖的必需场景数 ÷ 全部必需场景数 |
| Review Traceability | 当前数据集中真实存在的测试来源评论数 ÷ 全部被引用评论数 |
| Invalid References | 断裂的 Requirement、Finding、Review、优先级或证据关系数量 |

只有四项质量条件同时通过，结果才进入 UI。2026-07-18 已使用真实 DeepSeek 调用验证阶段 5：`REQ-001` 生成 `TC-001`～`TC-003`，覆盖 normal、negative、boundary，场景覆盖率与 Review Traceability 均为 100%，Invalid References 为 0。该数据仅验证流程，不代表真实 App Store 用户结论。

## 入口文件

`app.py` 是这个项目的入口。

执行 `.\.venv\Scripts\python.exe -m streamlit run app.py` 后，Streamlit 会启动本地服务器并在浏览器中展示页面。
