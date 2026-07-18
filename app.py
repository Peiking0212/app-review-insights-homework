"""ReviewScope AI 的第一个可运行版本。

启动命令：py -m streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.cleaning import CleaningReport, clean_review_records


PROJECT_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = PROJECT_DIR / "data" / "sample_reviews.json"
REQUIRED_COLUMNS = {"review_id", "rating", "content"}


def load_sample_reviews() -> pd.DataFrame:
    """读取项目自带的示例评论。"""
    with SAMPLE_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)
    return pd.DataFrame(records)


def load_uploaded_reviews(uploaded_file) -> pd.DataFrame:
    """根据扩展名读取用户上传的 CSV 或 JSON。"""
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if uploaded_file.name.lower().endswith(".json"):
        records = json.load(uploaded_file)
        return pd.DataFrame(records)
    raise ValueError("仅支持 CSV 或 JSON 文件。")


def validate_reviews(dataframe: pd.DataFrame) -> list[str]:
    """检查最基本的评论字段是否存在。"""
    missing = sorted(REQUIRED_COLUMNS - set(dataframe.columns))
    if not missing:
        return []
    return [f"缺少必要字段：{', '.join(missing)}"]


def normalize_reviews(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, CleaningReport]:
    """执行基础清洗，并保留每条清洗规则的统计结果。"""
    records, report = clean_review_records(dataframe.to_dict(orient="records"))
    if records:
        return pd.DataFrame(records).reset_index(drop=True), report
    return dataframe.iloc[0:0].copy(), report


def render_sidebar() -> tuple[pd.DataFrame, str]:
    """渲染输入区域并返回评论数据和用户的分析目标。"""
    st.sidebar.header("开始分析")
    source = st.sidebar.radio(
        "数据来源",
        ["内置示例数据", "上传 CSV / JSON"],
    )
    goal = st.sidebar.text_area(
        "分析目标",
        value="了解用户最主要的不满，并找出优先改进方向",
        help="第一版先保存这个目标，后续版本会将它发送给 AI。",
    )

    if source == "上传 CSV / JSON":
        uploaded_file = st.sidebar.file_uploader(
            "选择评论文件",
            type=["csv", "json"],
        )
        if uploaded_file is None:
            st.sidebar.info("尚未上传文件，暂时显示内置示例数据。")
            return load_sample_reviews(), goal
        return load_uploaded_reviews(uploaded_file), goal

    return load_sample_reviews(), goal


def main() -> None:
    st.set_page_config(
        page_title="ReviewScope AI",
        page_icon="🔎",
        layout="wide",
    )

    st.title("🔎 ReviewScope AI")
    st.caption("把真实用户评论转化为可执行产品改进方案")

    try:
        raw_reviews, analysis_goal = render_sidebar()
    except (ValueError, json.JSONDecodeError, pd.errors.ParserError) as error:
        st.error(f"文件读取失败：{error}")
        st.stop()

    errors = validate_reviews(raw_reviews)
    if errors:
        for error in errors:
            st.error(error)
        st.info("文件至少需要 review_id、rating、content 三列。")
        st.stop()

    cleaned_reviews, cleaning_report = normalize_reviews(raw_reviews)

    st.subheader("本次目标")
    st.info(analysis_goal)

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("原始评论", len(raw_reviews))
    metric_2.metric("有效评论", len(cleaned_reviews))
    metric_3.metric("清洗移除", cleaning_report.removed_count)
    average_rating = cleaned_reviews["rating"].mean()
    metric_4.metric(
        "平均评分",
        f"{average_rating:.1f}" if pd.notna(average_rating) else "暂无",
    )

    overview_tab, cleaning_tab, reviews_tab, workflow_tab = st.tabs(
        ["数据概览", "清洗过程", "评论数据", "工作流程"]
    )

    with overview_tab:
        st.subheader("评分分布")
        rating_counts = (
            cleaned_reviews["rating"]
            .value_counts()
            .reindex([1, 2, 3, 4, 5], fill_value=0)
            .rename_axis("评分")
            .rename("评论数量")
        )
        st.bar_chart(rating_counts)
        st.caption("图表和数量由 Python 根据当前评论计算。")

    with cleaning_tab:
        st.subheader("评论清洗过程")
        st.markdown(
            "清洗由确定性 Python 规则完成，不调用大模型。"
            "每条评论只会在首次命中的规则中计数，因此各步骤数量不会重复。"
        )
        retention_column, removed_column = st.columns(2)
        retention_column.metric(
            "数据保留率",
            f"{cleaning_report.retention_rate:.1%}",
        )
        removed_column.metric("总移除数量", cleaning_report.removed_count)
        st.dataframe(
            pd.DataFrame(cleaning_report.as_table_rows()),
            width="stretch",
            hide_index=True,
        )
        with st.expander("为什么需要这些规则？"):
            st.markdown(
                """
                - **稳定 ID**：后续 Finding、PRD 和测试用例都需要回到真实评论。
                - **合法评分**：避免错误评分影响评分分布和优先级判断。
                - **有效正文**：没有正文的记录无法提供产品问题证据。
                - **去重**：避免重复评论被多次计数，夸大某个问题的严重程度。
                - **保留原始数据**：清洗只生成新的分析数据，不覆盖上传的原始文件。
                """
            )

    with reviews_tab:
        st.subheader("清洗后的评论")
        preferred_columns = [
            column
            for column in [
                "review_id",
                "rating",
                "title",
                "content",
                "version",
                "published_at",
                "source_id",
                "storefront",
                "source",
            ]
            if column in cleaned_reviews.columns
        ]
        st.dataframe(
            cleaned_reviews[preferred_columns],
            width="stretch",
            hide_index=True,
        )

    with workflow_tab:
        st.subheader("当前完成情况")
        st.success("✅ 1. 读取示例数据或上传文件")
        st.success("✅ 2. 检查必要字段")
        st.success(
            "✅ 3. 过滤无效评分、空评论和重复评论，生成清洗审计报告"
        )
        st.info("⏳ 4. AI 动态主题发现（下一阶段）")
        st.info("⏳ 5. 生成问题、PRD 和测试用例（后续阶段）")

    st.divider()
    st.caption(
        "这是第一个可运行版本：它只负责读取、清洗和展示评论，暂未调用 AI。"
    )


if __name__ == "__main__":
    main()
