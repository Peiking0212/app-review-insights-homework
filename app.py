"""ReviewScope AI 的第一个可运行版本。

启动命令：py -m streamlit run app.py
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from src.cleaning import CleaningReport, clean_review_records
from src.config import ModelConfigError, model_configured
from src.finding_analysis import (
    FindingAnalysisService,
    FindingGenerationError,
    calculate_finding_quality,
)
from src.schemas import FindingGenerationResult, TopicDiscoveryResult
from src.topic_discovery import (
    TopicDiscoveryError,
    TopicDiscoveryService,
    prepare_reviews,
)


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
        help="动态主题会结合这个目标，但不会使用写死的行业分类。",
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


def analysis_fingerprint(records: list[dict], goal: str) -> str:
    """标识当前输入，避免切换数据后误显示旧主题。"""
    serialized = json.dumps(
        {"reviews": records, "goal": goal},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def finding_input_fingerprint(
    topic_result: TopicDiscoveryResult, review_fingerprint: str
) -> str:
    """标识 Finding 的上游输入，防止 Topic 重跑后显示旧问题。"""
    serialized = json.dumps(
        {
            "review_fingerprint": review_fingerprint,
            "topic_result": topic_result.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def render_topic_result(
    result: TopicDiscoveryResult, review_records: list[dict]
) -> None:
    """展示模型输出以及能够下钻查看的原始评论证据。"""
    review_by_id = {record["review_id"]: record for record in review_records}
    insight_by_id = {insight.insight_id: insight for insight in result.insights}
    evidence_review_ids = {insight.review_id for insight in result.insights}
    topic_column, insight_column, review_column, other_column = st.columns(4)
    topic_column.metric("动态主题", len(result.topics))
    insight_column.metric("原子观点", len(result.insights))
    review_column.metric("涉及评论（去重）", len(evidence_review_ids))
    other_column.metric("OTHER / 无法判断", len(result.other_review_ids))

    st.subheader("动态主题")
    if not result.topics:
        st.info("当前评论没有形成可用主题；请查看 OTHER 和数据限制。")
    for topic in result.topics:
        with st.expander(f"{topic.topic_id} · {topic.name}", expanded=True):
            st.write(topic.description)
            topic_review_ids = {
                insight_by_id[insight_id].review_id
                for insight_id in topic.insight_ids
                if insight_id in insight_by_id
            }
            st.caption(
                f"包含 {len(topic.insight_ids)} 条原子观点；"
                f"涉及 {len(topic_review_ids)} 条去重评论；"
                f"代表评论：{', '.join(topic.representative_review_ids)}"
            )
            for review_id in topic.representative_review_ids:
                review = review_by_id[review_id]
                st.markdown(
                    f"> **{review_id} · {review['rating']} 星**  "
                    f"\n> {review['content']}"
                )

    st.subheader("Atomic Insights（原子观点）")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Insight ID": insight.insight_id,
                    "Review ID": insight.review_id,
                    "情绪": insight.sentiment,
                    "原子观点": insight.statement,
                }
                for insight in result.insights
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    if result.other_review_ids:
        st.subheader("OTHER / 无法判断")
        st.write("、".join(result.other_review_ids))
    if result.limitations:
        st.subheader("数据限制")
        for limitation in result.limitations:
            st.warning(limitation)


def render_finding_result(
    result: FindingGenerationResult,
    topic_result: TopicDiscoveryResult,
    review_records: list[dict],
) -> None:
    """展示 Finding、支持证据、冲突证据和 Discovery。"""
    review_by_id = {record["review_id"]: record for record in review_records}
    quality = calculate_finding_quality(
        result, topic_result, set(review_by_id)
    )
    st.subheader("Finding Quality · Groundedness Score")
    coverage_column, traceability_column, unsupported_column, conflict_column = (
        st.columns(4)
    )
    coverage_column.metric(
        "Evidence Coverage", f"{quality.evidence_coverage:.0f}%"
    )
    traceability_column.metric(
        "Review Traceability", f"{quality.review_traceability:.0f}%"
    )
    unsupported_column.metric("Unsupported Claims", quality.unsupported_claims)
    conflict_column.metric("Conflict Evidence", quality.conflict_evidence)
    st.caption(
        f"覆盖 {quality.covered_review_count}/{quality.topic_review_count} "
        "条 Topic 去重评论；"
        f"可追溯 {quality.traceable_review_count}/"
        f"{quality.referenced_review_count} 条被引用评论。所有指标由 Python 复算。"
    )
    if quality.quality_gate_passed:
        st.success("Finding Quality Gate：通过")
    else:
        st.error(
            "Finding Quality Gate：未通过，请检查引用完整性和不受支持结论"
        )

    unique_support_ids = {
        review_id
        for finding in result.findings
        for review_id in finding.supporting_review_ids
    }
    finding_column, support_column, discovery_column = st.columns(3)
    finding_column.metric("Evidence Findings", len(result.findings))
    support_column.metric("支持评论（去重）", len(unique_support_ids))
    discovery_column.metric("Discovery 线索", len(result.discovery_items))

    if not result.findings:
        st.info("当前没有达到最小证据门槛的问题，请查看 Discovery。")
    for finding in result.findings:
        with st.expander(
            f"{finding.finding_id} · {finding.title}", expanded=True
        ):
            st.write(finding.description)
            severity_column, confidence_column, evidence_column, conflict_column = (
                st.columns(4)
            )
            severity_column.metric("严重度", finding.severity)
            confidence_column.metric("置信度", finding.confidence)
            evidence_column.metric(
                "支持评论", len(set(finding.supporting_review_ids))
            )
            conflict_column.metric(
                "冲突评论", len(set(finding.conflicting_review_ids))
            )
            st.caption(
                "来源 Topic：" + "、".join(finding.source_topic_ids)
            )

            st.markdown("**支持证据**")
            for review_id in finding.supporting_review_ids:
                review = review_by_id[review_id]
                st.markdown(
                    f"> **{review_id} · {review['rating']} 星**  "
                    f"\n> {review['content']}"
                )
            st.markdown("**冲突证据**")
            if finding.conflicting_review_ids:
                for review_id in finding.conflicting_review_ids:
                    review = review_by_id[review_id]
                    st.markdown(
                        f"> **{review_id} · {review['rating']} 星**  "
                        f"\n> {review['content']}"
                    )
            else:
                st.caption("当前数据中没有识别到直接冲突证据。")
            for limitation in finding.limitations:
                st.warning(limitation)

    if result.discovery_items:
        st.subheader("Discovery：证据不足，暂不进入产品规划")
        for item in result.discovery_items:
            with st.expander(f"{item.discovery_id} · {item.title}"):
                st.write(item.reason)
                st.caption(
                    "来源 Topic："
                    + "、".join(item.source_topic_ids)
                    + "；评论："
                    + "、".join(item.review_ids)
                )
                for review_id in item.review_ids:
                    review = review_by_id[review_id]
                    st.markdown(
                        f"> **{review_id} · {review['rating']} 星**  "
                        f"\n> {review['content']}"
                    )

    if result.limitations:
        st.subheader("整体数据限制")
        for limitation in result.limitations:
            st.warning(limitation)


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

    try:
        prepared_reviews = prepare_reviews(
            cleaned_reviews.to_dict(orient="records")
        )
    except ValidationError as error:
        st.error(f"评论无法进入 AI 分析阶段：{error}")
        st.stop()
    prepared_records = [
        review.model_dump(mode="json") for review in prepared_reviews
    ]
    current_fingerprint = analysis_fingerprint(prepared_records, analysis_goal)

    if model_configured():
        if st.session_state.get("model_call_verified"):
            st.sidebar.success("模型调用：已验证")
        else:
            st.sidebar.info("模型配置：已读取（尚未验证调用）")
    else:
        st.sidebar.warning("模型配置：未完成（参照 .env.example）")

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

    (
        overview_tab,
        cleaning_tab,
        reviews_tab,
        topics_tab,
        findings_tab,
        workflow_tab,
    ) = st.tabs(
        [
            "数据概览",
            "清洗过程",
            "评论数据",
            "动态主题",
            "Evidence Finding",
            "工作流程",
        ]
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
            pd.DataFrame(prepared_records)[preferred_columns],
            width="stretch",
            hide_index=True,
        )

    with topics_tab:
        st.subheader("阶段 2：动态主题发现")
        st.markdown(
            "AI 会先从每条评论提取单一观点，再根据本次数据聚合主题。"
            "主题不是预设分类；Python 会校验所有 Review / Insight 引用。"
        )
        if any(review.source == "illustrative_sample" for review in prepared_reviews):
            st.warning(
                "当前包含内置演示评论。这里的 AI 结果只能验证流程，"
                "不能作为最终 Homework 的真实用户结论。"
            )

        if st.button("开始动态主题分析", type="primary"):
            st.session_state.pop("topic_result", None)
            st.session_state.pop("topic_fingerprint", None)
            st.session_state.pop("finding_result", None)
            st.session_state.pop("finding_fingerprint", None)
            try:
                with st.spinner("正在提取 Atomic Insight 并聚合动态主题……"):
                    result = TopicDiscoveryService().discover(
                        prepared_reviews, analysis_goal
                    )
            except (ModelConfigError, TopicDiscoveryError) as error:
                st.session_state["model_call_verified"] = False
                st.error(str(error))
                st.info("主题阶段已停止，不会生成 Finding、PRD 或测试用例。")
            else:
                st.session_state["model_call_verified"] = True
                st.session_state["topic_result"] = result.model_dump(mode="json")
                st.session_state["topic_fingerprint"] = current_fingerprint
                st.success("动态主题发现完成，引用校验通过。")

        saved_result = st.session_state.get("topic_result")
        saved_fingerprint = st.session_state.get("topic_fingerprint")
        if saved_result and saved_fingerprint == current_fingerprint:
            render_topic_result(
                TopicDiscoveryResult.model_validate(saved_result),
                prepared_records,
            )
        elif saved_result:
            st.info("输入数据或分析目标已改变，请重新运行动态主题发现。")

    with findings_tab:
        st.subheader("阶段 3：Evidence Finding")
        st.markdown(
            "模型负责草拟具体问题和冲突观点；Python 负责校验证据、"
            "计算支持评论数和置信度。少于 2 条去重支持评论的候选会进入 Discovery。"
        )
        saved_topic_result = st.session_state.get("topic_result")
        saved_topic_fingerprint = st.session_state.get("topic_fingerprint")
        current_topic_result = None
        if (
            saved_topic_result
            and saved_topic_fingerprint == current_fingerprint
        ):
            current_topic_result = TopicDiscoveryResult.model_validate(
                saved_topic_result
            )

        if current_topic_result is None:
            st.info("请先在“动态主题”标签完成阶段 2，Finding 不会绕过 Topic 生成。")
        else:
            current_finding_fingerprint = finding_input_fingerprint(
                current_topic_result, current_fingerprint
            )
            if st.button("生成 Evidence Finding", type="primary"):
                st.session_state.pop("finding_result", None)
                st.session_state.pop("finding_fingerprint", None)
                try:
                    with st.spinner("正在归纳问题并执行 Evidence 质量门……"):
                        finding_result = FindingAnalysisService().generate(
                            prepared_reviews,
                            current_topic_result,
                            analysis_goal,
                        )
                except (ModelConfigError, FindingGenerationError) as error:
                    st.error(str(error))
                    st.info("Finding 阶段已停止，不会生成 PRD 或测试用例。")
                else:
                    st.session_state["finding_result"] = (
                        finding_result.model_dump(mode="json")
                    )
                    st.session_state["finding_fingerprint"] = (
                        current_finding_fingerprint
                    )
                    st.success("Evidence Finding 生成完成，质量门校验通过。")

            saved_finding_result = st.session_state.get("finding_result")
            saved_finding_fingerprint = st.session_state.get(
                "finding_fingerprint"
            )
            if (
                saved_finding_result
                and saved_finding_fingerprint == current_finding_fingerprint
            ):
                render_finding_result(
                    FindingGenerationResult.model_validate(saved_finding_result),
                    current_topic_result,
                    prepared_records,
                )
            elif saved_finding_result:
                st.info("上游 Topic 已改变，请重新生成 Evidence Finding。")

    with workflow_tab:
        st.subheader("当前完成情况")
        st.success("✅ 1. 读取示例数据或上传文件")
        st.success("✅ 2. 检查必要字段")
        st.success(
            "✅ 3. 过滤无效评分、空评论和重复评论，生成清洗审计报告"
        )
        st.success("✅ 4. AI 动态主题发现、OTHER 与引用校验")
        st.success("✅ 5. Evidence Finding、冲突证据与置信度质量门")
        st.info("⏳ 6. 生成版本规划、PRD 和测试用例（后续阶段）")

    st.divider()
    st.caption(
        "当前版本已支持动态主题与 Evidence Finding；PRD 和测试用例仍未生成。"
    )


if __name__ == "__main__":
    main()
