# ReviewScope AI 开发日志与执行看板

## 1. 项目信息

- 项目：LAIEN App Review Insights Homework
- 当前目录：`E:\Codex\Projects\Study\app-review-insights`
- 入口文件：`app.py`
- 推荐技术栈：Python + Streamlit + Pandas + Pydantic + OpenAI-compatible API
- 提交截止：2026-07-20 10:00（提交前应再次确认 HR 通知）


## 2. 使用规则

每次开始开发：

1. 阅读 `AGENTS.md`、`AI_USAGE.md` 和本文件。
2. 查看 Git 状态，不覆盖用户修改。
3. 运行当前测试和语法检查。
4. 只选择一个“下一任务”完成。

每次结束开发：

1. 运行测试。
2. 更新阶段状态和当天日志。
3. 记录错误、取舍和下一步。
4. 一个独立阶段通过验收后创建 Git commit。

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

- 状态：待开始
- 任务：
  - [ ] 添加 `.env.example` 和模型客户端。
  - [ ] 使用结构化输出生成动态 Topic。
  - [ ] 禁止写死健身 App 分类。
  - [ ] 支持 OTHER/无法判断。
  - [ ] 模型失败时显示错误，不生成下游结果。
- 验收：更换评论数据后主题发生合理变化，结构校验通过。
- 建议 commit：`feat: add model-driven dynamic topic discovery`

### 阶段 3：Evidence Finding

- 状态：待开始
- 任务：
  - [ ] 每个 Finding 返回支持和冲突 Review ID。
  - [ ] Python 检查 Review ID。
  - [ ] Python 计算支持数量。
  - [ ] 数据不足时降低置信度或放入 Discovery。
- 验收：不存在非法引用；每个 Finding 可展开真实评论。
- 建议 commits：
  - `feat: generate evidence-grounded findings`
  - `fix: reject hallucinated review references`

### 阶段 4：版本规划与 PRD

- 状态：待开始
- 任务：
  - [ ] 按证据、严重度、目标相关性和范围规划版本。
  - [ ] 生成 3–6 条核心 Requirement。
  - [ ] 每条包含来源、范围、不包含范围和验收标准。
  - [ ] 无证据建议标记为 Product Hypothesis。
- 验收：所有 Requirement 能追溯到 Finding 和 Review。
- 建议 commit：`feat: generate evidence-based release plan and PRD`

### 阶段 5：测试用例与追溯检查

- 状态：待开始
- 任务：
  - [ ] 每个 P0/P1 Requirement 生成正常和异常测试用例。
  - [ ] 校验 TestCase → Requirement → Review。
  - [ ] 展示追溯矩阵和覆盖率。
- 验收：非法引用为 0；核心需求测试覆盖率为 100%。
- 建议 commit：`feat: add traceable test cases and quality gate`

### 阶段 6：美国区 App Store 采集

- 状态：待开始
- 任务：
  - [ ] 解析 App Store URL 和 App ID。
  - [ ] 强制使用美国区评论。
  - [ ] 分页、限速、超时和有限重试。
  - [ ] 记录采集时间、来源和限制。
- 验收：题目链接可以获取真实评论；失败时保留上传和缓存路径。
- 建议 commit：`feat: add US App Store review collection`

### 阶段 7：缓存 Demo、导出和错误恢复

- 状态：待开始
- 任务：
  - [ ] 保存一次真实、经过校验的分析缓存。
  - [ ] 无 Key/无网络时一键加载缓存。
  - [ ] 导出 PRD Markdown、测试 CSV 和完整 JSON。
  - [ ] 保留已完成阶段，支持失败提示或单阶段重试。
- 验收：断网情况下仍能演示完整结果。
- 建议 commit：`feat: add offline demo exports and recovery`

### 阶段 8：最终交付

- 状态：待开始
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

> 完成阶段 2：实现基于当前评论动态生成 Topic 的第一版，不接 App Store 实时采集，不生成 PRD。

建议交给 AI 的提示：

```text
请先阅读 AGENTS.md、AI_USAGE.md 和 DEVELOPMENT_LOG.md。
完成阶段 2：添加 OpenAI-compatible 模型客户端和动态主题发现。
主题必须根据当前评论产生，不能写死健身 App 分类；输出使用 Topic Schema，支持 OTHER，模型失败时停止下游流程。
保持现有 Streamlit 页面可以运行，不做 App Store 实时采集，不生成 Finding 或 PRD。
完成后运行全部测试，更新 DEVELOPMENT_LOG.md，并在检查 diff 后创建一个 Git commit；不要推送。
```

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
