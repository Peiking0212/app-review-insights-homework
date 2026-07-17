# ReviewScope AI

这是 App Review Insights Homework 的第一个可运行版本。

当前版本已经可以：

- 加载内置示例评论；
- 上传 CSV 或 JSON 评论文件；
- 检查必要字段；
- 删除空评论、异常评分和重复评论；
- 展示数据统计、评分分布和评论表格。

当前版本还没有接入 AI，也不会生成 PRD。后续会在这个基础上逐步增加动态主题、用户问题、产品需求、测试用例和追溯检查。

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

## 入口文件

`app.py` 是这个项目的入口。

执行 `.\.venv\Scripts\python.exe -m streamlit run app.py` 后，Streamlit 会启动本地服务器并在浏览器中展示页面。
