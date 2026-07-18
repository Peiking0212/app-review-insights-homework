# ReviewScope AI

这是 App Review Insights Homework 的阶段 2 可运行版本。

当前版本已经可以：

- 加载内置示例评论；
- 上传 CSV 或 JSON 评论文件；
- 检查必要字段；
- 删除空评论、异常评分和重复评论；
- 展示每条清洗规则、移除数量、保留率和规则原因；
- 展示数据统计、评分分布和评论表格；
- 使用 AI 提取 Atomic Insight，并根据当前评论动态聚合 Topic；
- 支持 OTHER / 无法判断，使用 Python 拦截不存在、重复或遗漏的引用。

当前版本不会生成 Finding 或 PRD。后续会在已经通过校验的 Topic 基础上增加用户问题、产品需求、测试用例和完整追溯检查。

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

使用 OpenAI 官方接口时 `OPENAI_BASE_URL` 可以留空；使用兼容接口时，填写服务商提供的 `/v1` 地址。`.env` 已被 Git 忽略，不能把真实密钥提交到 GitHub。

启动网站：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

终端会显示一个本地地址，通常是：

```text
http://localhost:8501
```

用浏览器打开这个地址即可。

## 上传文件格式

CSV 或 JSON 至少需要这三个字段：

```text
review_id
rating
content
```

其他字段，例如 `title`、`version` 和 `published_at`，可以暂时缺少。

内置示例数据标记为 `illustrative_sample`，只用于验证页面和清洗流程，不能作为最终分析中的真实用户证据。最终演示必须替换为可说明来源的美国区真实评论或透明标记的缓存结果。

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
→ AI 提取单一方面、单一主要情绪的 Atomic Insight
→ AI 根据本次 Insight 动态聚合 Topic
→ Python 校验 Review / Insight 引用
→ UI 展示主题、原子观点、代表评论和限制
```

提示词明确禁止预设健身、订阅、广告等行业分类。每条 Insight 必须归入且只归入一个 Topic；无法提供有效产品体验信息的评论进入 `OTHER`。如果 API、网络、结构化输出或引用校验失败，本阶段会停止，不会继续生成没有证据的 Finding 或 PRD。

内置数据只能验证这条流程。由于本地没有保存真实 API Key，本次提交完成了代码、失败路径和客户端兼容性测试，但仍需使用自己的 Key 和至少两组不同评论做一次真实模型验收。

## 入口文件

`app.py` 是这个项目的入口。

执行 `.\.venv\Scripts\python.exe -m streamlit run app.py` 后，Streamlit 会启动本地服务器并在浏览器中展示页面。
