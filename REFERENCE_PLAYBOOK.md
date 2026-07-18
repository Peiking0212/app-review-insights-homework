# ReviewScope AI 项目参考与借鉴手册

## 1. 目的

本手册不是“照抄清单”，而是项目每个阶段的学习路由。开始一个阶段前，只查看与当前问题直接相关的案例，提取可验证的设计原则，再结合 Homework 的范围实现最小闭环。

固定原则：

```text
先确认当前阶段
→ 查看对应案例
→ 记录借鉴与不借鉴内容
→ 实现最小功能
→ 用测试和真实数据验证
→ 更新开发日志
```

任何外部案例都不能替代题目要求、真实评论证据和本项目测试。复制代码前必须检查许可证、依赖、维护状态和数据限制。

## 2. 总体借鉴架构

| 组件或案例 | 在本项目中的职责 | 主要借鉴内容 | 不直接照搬的内容 |
|---|---|---|---|
| App Store Scraper | 真实评论采集 | 美国区参数、评论字段、分页、限速和失败处理 | 不把第三方库当成唯一数据源，不隐瞒接口限制 |
| Apple Review Summarization Pipeline | 分析流程设计 | 原子 Insight、动态主题、代表性证据、平衡观点和 Groundedness | 不训练 Apple 的内部模型，不只生成一段摘要 |
| LLM | 语义分析与内容草拟 | 原子 Insight、动态主题、Finding、需求和测试草稿 | 不让模型统计数量，不接受无证据结论 |
| Instructor + Pydantic | 稳定结构化输出 | JSON Schema、字段验证、失败重试和类型约束 | 结构正确不代表事实正确，仍需 Python 校验引用 |
| Python Validator | 证据与追溯校验 | ID 存在性、数量、覆盖率、冲突证据和无依据结论拦截 | 不用模糊的 LLM 自评替代确定性检查 |
| Streamlit | 工作流和结果展示 | 输入控件、阶段状态、Tab、中间产物、错误和下载 | 不在核心闭环完成前投入复杂动画和无关页面 |
| Rereflect | UI 信息层级参考 | Top Pain Points、mentions、筛选、趋势、证据下钻 | 不实现 CRM、流失预测、团队协作等超出题目范围的功能 |

## 3. 参考资料

### App Store Scraper

- 参考项目：[cowboy-bebug/app-store-scraper](https://github.com/cowboy-bebug/app-store-scraper)
- 查看时重点回答：
  - 如何明确使用 `country="us"`？
  - App ID、评论字段和分页是怎样处理的？
  - 请求频率、最大数量和异常有什么限制？
  - 第三方库失败时怎样降级到 CSV、JSON 或缓存？

### Apple Review Summarization Pipeline

- 参考资料：[Apple - An LLM-Based Approach to Review Summarization on the App Store](https://machinelearning.apple.com/research/app-store-review)
- 查看时重点回答：
  - 为什么先从单条评论提取原子 Insight？
  - 为什么主题需要动态生成而不是固定分类？
  - 怎样选择代表性证据并兼顾正反观点？
  - 怎样评价 Groundedness、Helpfulness 和准确性？

### LLM

- 使用 OpenAI-compatible 接口，具体服务商由本地 `.env` 配置。
- 查看模型文档时重点回答：
  - 是否支持 JSON Schema 或结构化输出？
  - 上下文、超时、速率和费用限制是什么？
  - 模型失败、拒答或返回非法 JSON 时怎样停止下游流程？
- 禁止把 API Key 写入仓库或聊天记录。

### Instructor + Pydantic

- 参考项目：[Instructor](https://github.com/567-labs/instructor)
- 参考文档：[Pydantic Documentation](https://docs.pydantic.dev/)
- 查看时重点回答：
  - 如何把模型输出直接验证为 Pydantic 对象？
  - 哪些错误适合有限重试，哪些错误必须中止？
  - Schema 如何约束 Topic、Finding、Requirement 和 TestCase？

### Python Validator

- 本项目内部实现，不依赖单一外部框架。
- 必须检查：
  - Topic 引用的 Review ID 是否存在；
  - Finding 的支持与冲突 Review ID 是否存在且不重叠；
  - Requirement 是否关联有效 Finding 和 Review；
  - TestCase 是否关联有效 Requirement 和 Review；
  - 数量是否由真实引用计算；
  - 无证据内容是否被阻止或标记为 Product Hypothesis。

### Streamlit

- 参考文档：[Streamlit Documentation](https://docs.streamlit.io/)
- 查看时重点回答：
  - 怎样保存阶段状态和中间结果？
  - 怎样展示运行进度、失败原因和重试入口？
  - 怎样展示数据表格、证据详情和导出按钮？

### Rereflect

- 产品参考：[Rereflect](https://www.rereflect.ca/)
- 查看时重点回答：
  - Top Pain Points 为什么能被快速理解？
  - mentions、趋势、筛选和原始反馈如何形成信息层级？
  - 用户怎样从结论下钻到证据？
- 只参考信息架构，不复制品牌、视觉素材或无关业务功能。

## 4. 分阶段查看路线

| 项目阶段 | 开始前必须查看 | 本阶段要借鉴的结果 |
|---|---|---|
| 阶段 0：导入、清洗与统计 | Apple Pipeline、Python Validator 原则 | 过滤噪声、确定性统计、保留原始数据 |
| 阶段 1：可追溯数据模型 | Pydantic、Instructor 基础示例 | 五类对象 Schema、证据字段和失败验证 |
| 阶段 2：动态主题发现 | Apple Pipeline、Instructor、所选 LLM 文档 | 原子 Insight、动态 Topic、结构化输出和失败停止 |
| 阶段 3：Evidence Finding | Apple Pipeline、Python Validator | 代表性证据、冲突观点、置信度和非法 ID 拦截 |
| 阶段 4：版本规划与 PRD | Apple Pipeline、Python Validator | 证据驱动优先级、范围、不包含范围和验收标准 |
| 阶段 5：测试与追溯 | Python Validator | Review → Finding → Requirement → TestCase 完整校验 |
| 阶段 6：App Store 采集 | App Store Scraper | 美国区、分页、限速、来源记录和失败降级 |
| 阶段 7：缓存、导出与恢复 | Streamlit、Rereflect | 中间状态、错误提示、缓存 Demo 和结果导出 |
| 阶段 8：最终交付 | Streamlit、Rereflect | 信息层级、演示路径和 README 易用性 |

## 5. 每阶段的借鉴记录模板

开始开发前，在 `DEVELOPMENT_LOG.md` 当前任务中填写：

```markdown
### 阶段参考检查

- 当前阶段：
- 查看资料：
- 学到的关键做法：
- 本项目准备借鉴：
- 本项目明确不借鉴：
- 不借鉴原因：
- 本阶段验收方式：
```

阶段结束后补充：

```markdown
- 实际采用：
- 与参考案例的差异：
- 测试或真实数据验证：
- 遗留限制：
```

## 6. 截止时间保护规则

- 每阶段最多选择 1～2 个主要案例，不进行无目的的大范围调研。
- 查看案例的目标是回答当前问题，不是重建对方完整产品。
- 参考架构与当前 P0 冲突时，以 Homework 明确要求和稳定演示为优先。
- 如果参考项目依赖过重，先实现轻量版本，并把完整版记录为后续方向。
- 任何借鉴都必须能够由本人在现场用自己的话解释。
