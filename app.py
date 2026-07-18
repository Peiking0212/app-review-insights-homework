"""ReviewScope AI 的第一个可运行版本。

启动命令：py -m streamlit run app.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from pydantic import ValidationError

from src.app_store import (
    AppStoreCollectionError,
    CollectionReport,
    collect_us_reviews,
)
from src.analysis_cache import (
    AnalysisCacheError,
    AnalysisSnapshot,
    create_snapshot,
    load_snapshot,
    promote_complete_demo,
    save_snapshot,
)
from src.cleaning import CleaningReport, clean_review_records
from src.config import ModelConfig, ModelConfigError, model_configured
from src.finding_analysis import (
    FindingAnalysisService,
    FindingGenerationError,
    calculate_finding_quality,
)
from src.product_planning import ProductPlanningError, ProductPlanningService
from src.schemas import (
    FindingGenerationResult,
    ProductPlanResult,
    TestGenerationResult,
    TopicDiscoveryResult,
)
from src.test_generation import (
    TestGenerationError,
    TestGenerationService,
    calculate_traceability_quality,
)
from src.topic_discovery import (
    TopicDiscoveryError,
    TopicDiscoveryService,
    prepare_reviews,
)


PROJECT_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = PROJECT_DIR / "data" / "sample_reviews.json"
DEMO_SNAPSHOT_FILE = PROJECT_DIR / "data" / "demo_snapshot.json"
RUNTIME_CHECKPOINT_FILE = PROJECT_DIR / "data" / "runtime" / "last_success.json"
REQUIRED_COLUMNS = {"review_id", "rating", "content"}
PAGE_SECTIONS = (
    "数据概览",
    "清洗过程",
    "评论数据",
    "动态主题",
    "Evidence Finding",
    "版本规划与 PRD",
    "测试用例与追溯",
    "工作流程",
)


def render_editorial_theme() -> None:
    """应用黑白编辑风设计令牌，不改变任何业务逻辑。"""
    st.markdown(
        """
        <style>
        :root {
            --rs-ink: #111217;
            --rs-muted: #727782;
            --rs-canvas: #f3f5f7;
            --rs-surface: #ffffff;
            --rs-soft: #f7f8fa;
            --rs-line: #e5e7eb;
            --rs-radius: 20px;
        }
        html, body, .stApp {
            font-family: Inter, Manrope, "PingFang SC", "Microsoft YaHei",
                system-ui, sans-serif;
        }
        .stApp {
            background: var(--rs-canvas);
            color: var(--rs-ink);
        }
        [data-testid="stAppViewBlockContainer"] {
            max-width: 1440px;
            padding-top: 5rem;
            padding-bottom: 4rem;
        }
        [data-testid="stSidebar"] {
            min-width: 280px;
            max-width: 280px;
            background: #fbfbfa;
            border-right: 1px solid var(--rs-line);
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.25rem;
        }
        h1, h2, h3 {
            color: var(--rs-ink);
            letter-spacing: -0.025em;
        }
        h1 {
            font-size: clamp(2rem, 3vw, 2.75rem) !important;
            font-weight: 780 !important;
            line-height: 1.08 !important;
        }
        h2, [data-testid="stHeadingWithActionElements"] h2 {
            font-size: 1.45rem !important;
            font-weight: 720 !important;
        }
        h3, [data-testid="stHeadingWithActionElements"] h3 {
            font-size: 1.08rem !important;
            font-weight: 680 !important;
        }
        p, label, [data-testid="stCaptionContainer"] {
            line-height: 1.65;
        }
        [data-testid="stCaptionContainer"] {
            color: var(--rs-muted);
        }
        [data-testid="stMetric"] {
            min-height: 116px;
            padding: 1rem 1.15rem;
            background: var(--rs-surface);
            border: 1px solid var(--rs-line);
            border-radius: var(--rs-radius);
            box-shadow: 0 10px 28px rgba(17, 18, 23, 0.035);
        }
        [data-testid="stMetricValue"] {
            color: var(--rs-ink);
            font-size: 2rem;
            font-weight: 760;
            letter-spacing: -0.035em;
        }
        [data-testid="stMetricLabel"] {
            color: var(--rs-muted);
            font-size: 0.78rem;
            font-weight: 650;
            letter-spacing: 0.02em;
        }
        .stButton > button,
        .stDownloadButton > button {
            min-height: 2.65rem;
            padding: 0.55rem 1.1rem;
            border: 1px solid #d9dce1;
            border-radius: 999px;
            background: #ffffff;
            color: var(--rs-ink);
            font-weight: 680;
            box-shadow: none;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: var(--rs-ink);
            color: var(--rs-ink);
        }
        .stButton > button[kind="primary"] {
            background: var(--rs-ink);
            border-color: var(--rs-ink);
            color: #ffffff;
        }
        [data-testid="stAlert"] {
            border: 1px solid var(--rs-line);
            border-radius: 16px;
            box-shadow: none;
        }
        [data-testid="stExpander"] {
            overflow: hidden;
            margin-bottom: 0.85rem;
            background: var(--rs-surface);
            border: 1px solid var(--rs-line);
            border-radius: var(--rs-radius);
            box-shadow: 0 10px 28px rgba(17, 18, 23, 0.025);
        }
        [data-testid="stDataFrame"] {
            overflow: hidden;
            border: 1px solid var(--rs-line);
            border-radius: 16px;
        }
        blockquote {
            margin: 0.65rem 0 !important;
            padding: 0.85rem 1rem !important;
            background: var(--rs-soft);
            border-left: 3px solid var(--rs-ink) !important;
            border-radius: 0 14px 14px 0;
            color: #33363d !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            padding: 0.55rem 0.7rem;
            border-radius: 12px;
            white-space: nowrap;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {
            display: none;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
            background: var(--rs-ink);
            color: #ffffff;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p,
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) span {
            color: #ffffff !important;
        }
        [data-testid="stIconMaterial"] {
            font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
            font-weight: normal !important;
            font-style: normal !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
        }
        #MainMenu,
        footer,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            display: none !important;
        }
        .rs-status-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 0;
            margin: 1.15rem 0 1.35rem;
            padding: 0.2rem 0;
            background: var(--rs-surface);
            border: 1px solid var(--rs-line);
            border-radius: 16px;
        }
        .rs-status-item {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            min-height: 44px;
            padding: 0 1rem;
            color: #42464f;
            font-size: 0.84rem;
            font-weight: 620;
        }
        .rs-status-item + .rs-status-item {
            border-left: 1px solid var(--rs-line);
        }
        .rs-status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--rs-ink);
        }
        .rs-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.45rem 0 1rem;
        }
        .rs-chip {
            display: inline-flex;
            align-items: center;
            min-height: 28px;
            padding: 0.15rem 0.7rem;
            border: 1px solid var(--rs-line);
            border-radius: 999px;
            background: var(--rs-soft);
            color: #4b4f58;
            font-size: 0.75rem;
            font-weight: 650;
        }
        .rs-chip--strong {
            background: var(--rs-soft);
            border-color: var(--rs-line);
            color: #4b4f58;
        }
        .rs-pipeline {
            min-height: 360px;
            padding: 1.15rem 1.25rem;
            background: var(--rs-surface);
            border: 1px solid var(--rs-line);
            border-radius: var(--rs-radius);
            box-shadow: 0 10px 28px rgba(17, 18, 23, 0.025);
        }
        .rs-pipeline-step {
            display: grid;
            grid-template-columns: 28px 1fr auto;
            gap: 0.7rem;
            align-items: center;
            padding: 0.65rem 0;
            border-bottom: 1px solid #eff0f2;
        }
        .rs-pipeline-step:last-child { border-bottom: 0; }
        .rs-step-icon {
            display: grid;
            width: 26px;
            height: 26px;
            place-items: center;
            border-radius: 50%;
            background: var(--rs-ink);
            color: white;
            font-size: 0.72rem;
            font-weight: 800;
        }
        .rs-step-title { font-size: 0.88rem; font-weight: 680; }
        .rs-step-meta { color: var(--rs-muted); font-size: 0.74rem; }
        .rs-step-state { color: var(--rs-muted); font-size: 0.72rem; }
        .rs-summary-panel {
            margin: 0.6rem 0 1.25rem;
            padding: 1rem 1.15rem;
            background: var(--rs-surface);
            border: 1px solid var(--rs-line);
            border-radius: 16px;
            color: #3f434b;
            line-height: 1.75;
        }
        .rs-workflow-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 1rem;
        }
        .rs-workflow-card {
            min-height: 132px;
            padding: 1rem;
            background: var(--rs-surface);
            border: 1px solid var(--rs-line);
            border-radius: 18px;
            box-shadow: 0 10px 28px rgba(17, 18, 23, 0.025);
        }
        .rs-workflow-index {
            display: grid;
            width: 30px;
            height: 30px;
            margin-bottom: 0.7rem;
            place-items: center;
            border-radius: 50%;
            background: var(--rs-ink);
            color: #ffffff;
            font-size: 0.75rem;
            font-weight: 760;
        }
        .rs-workflow-title {
            color: var(--rs-ink);
            font-size: 0.92rem;
            font-weight: 720;
        }
        .rs-workflow-copy {
            margin-top: 0.35rem;
            color: var(--rs-muted);
            font-size: 0.76rem;
            line-height: 1.55;
        }
        @media (max-width: 900px) {
            .rs-status-item + .rs-status-item { border-left: 0; }
            [data-testid="stMetric"] { min-height: 96px; }
            .rs-workflow-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_editorial_status_strip(
    demo_mode: bool, collection_report: CollectionReport | None
) -> None:
    """用紧凑状态条说明数据来源、运行模式和质量保障。"""
    source_label = (
        "真实美国区数据"
        if collection_report is not None
        and collection_report.storefront.lower() == "us"
        else "当前导入数据"
    )
    mode_label = "缓存演示模式" if demo_mode else "实时分析模式"
    quality_label = (
        "质量门全部通过"
        if st.session_state.get("test_result")
        else "确定性质量门已启用"
    )
    items = (source_label, mode_label, quality_label)
    markup = "".join(
        '<span class="rs-status-item"><span class="rs-status-dot"></span>'
        + escape(item)
        + "</span>"
        for item in items
    )
    st.markdown(
        f'<div class="rs-status-strip">{markup}</div>',
        unsafe_allow_html=True,
    )


def _result_count(session_key: str, field: str) -> int | None:
    """从当前已校验的结构化结果中读取展示数量。"""
    payload = st.session_state.get(session_key)
    if not isinstance(payload, dict):
        return None
    records = payload.get(field)
    return len(records) if isinstance(records, list) else None


def render_editorial_outcome_summary(cleaned_review_count: int) -> None:
    """在概览页集中展示 Review 到 TestCase 的核心产出。"""
    values = (
        ("评论", cleaned_review_count),
        ("动态主题", _result_count("topic_result", "topics")),
        ("核心问题", _result_count("finding_result", "findings")),
        ("产品需求", _result_count("planning_result", "requirements")),
        ("测试用例", _result_count("test_result", "test_cases")),
    )
    columns = st.columns(5)
    for column, (label, value) in zip(columns, values):
        column.metric(label, value if value is not None else "—")


def render_editorial_pipeline() -> None:
    """用确定性状态展示当前分析闭环完成度。"""
    steps = (
        ("数据采集", "评论已进入清洗流程", True),
        ("清洗与去重", "规则审计已完成", True),
        ("主题提取", "动态主题与原子观点", bool(st.session_state.get("topic_result"))),
        ("问题识别", "证据 Finding 与冲突观点", bool(st.session_state.get("finding_result"))),
        ("需求与测试", "PRD 和端到端追溯", bool(st.session_state.get("test_result"))),
    )
    rows = []
    for title, meta, completed in steps:
        rows.append(
            '<div class="rs-pipeline-step">'
            f'<span class="rs-step-icon">{"✓" if completed else "·"}</span>'
            '<span>'
            f'<span class="rs-step-title">{escape(title)}</span><br>'
            f'<span class="rs-step-meta">{escape(meta)}</span>'
            "</span>"
            f'<span class="rs-step-state">{"已完成" if completed else "待运行"}</span>'
            "</div>"
        )
    st.markdown(
        '<div class="rs-pipeline"><strong>分析流水线</strong>'
        + "".join(rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_editorial_chips(
    chips: tuple[tuple[str, bool], ...] | list[tuple[str, bool]]
) -> None:
    """渲染一组安全转义的黑白摘要标签。"""
    markup = "".join(
        '<span class="rs-chip'
        + (' rs-chip--strong' if strong else '')
        + f'">{escape(str(label))}</span>'
        for label, strong in chips
    )
    st.markdown(
        f'<div class="rs-chip-row">{markup}</div>',
        unsafe_allow_html=True,
    )


def render_editorial_workflow() -> None:
    """以紧凑卡片展示完整 Homework 工作流。"""
    stages = (
        ("数据输入", "示例、美国区采集或 CSV / JSON 导入"),
        ("确定性清洗", "字段校验、评分校验、空内容过滤与去重"),
        ("动态主题", "Atomic Insight 提取、主题聚合与引用校验"),
        ("证据发现", "支持证据、冲突观点、置信度与质量门"),
        ("版本与 PRD", "需求边界、版本规划、优先级和验收标准"),
        ("测试与追溯", "正常、异常、边界测试及端到端引用检查"),
        ("失败恢复", "阶段检查点、同输入恢复和真实缓存降级"),
        ("真实 Demo", "美国区公开评论和经过质量门的完整快照"),
        ("结果交付", "可审计的 Review 到 TestCase 产品闭环"),
    )
    cards = "".join(
        '<div class="rs-workflow-card">'
        f'<span class="rs-workflow-index">{index:02d}</span>'
        f'<div class="rs-workflow-title">{escape(title)}</div>'
        f'<div class="rs-workflow-copy">{escape(copy)}</div>'
        "</div>"
        for index, (title, copy) in enumerate(stages, start=1)
    )
    st.markdown(
        f'<div class="rs-workflow-grid">{cards}</div>',
        unsafe_allow_html=True,
    )


def keep_page_selected(page: str) -> None:
    """在阶段按钮触发整页重跑前，把当前结果页同步到侧栏导航。"""
    if page not in PAGE_SECTIONS:
        raise ValueError(f"未知页面：{page}")
    st.session_state["page_navigation"] = page


def sync_top_page_selection() -> None:
    """把顶部可控导航的选择同步到侧栏和阶段按钮共用的状态。"""
    page = st.session_state.get("top_page_navigation")
    if page in PAGE_SECTIONS:
        st.session_state["page_navigation"] = page


def render_back_to_top() -> None:
    """提供始终可见的一键回到顶部入口。"""
    st.markdown('<div id="page-top"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .back-to-top {
            position: fixed;
            right: 1.5rem;
            bottom: 1.5rem;
            z-index: 999999;
            padding: 0.55rem 0.85rem;
            border: 1px solid rgba(128, 128, 128, 0.35);
            border-radius: 999px;
            background: var(--background-color, white);
            color: var(--text-color, inherit) !important;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
            text-decoration: none !important;
            font-size: 0.9rem;
        }
        .back-to-top:hover {
            border-color: #111217;
            color: #111217 !important;
        }
        </style>
        <a class="back-to-top" href="#page-top" target="_self"
           aria-label="回到页面顶部">↑ 回到顶部</a>
        """,
        unsafe_allow_html=True,
    )


def render_page_navigation() -> str:
    """在固定侧边栏中选择要查看的结果区域。"""
    st.sidebar.divider()
    st.sidebar.subheader("页面快捷导航")
    selected_page = st.sidebar.radio(
        "直接前往",
        PAGE_SECTIONS,
        key="page_navigation",
        label_visibility="collapsed",
    )
    st.sidebar.caption("选择后会自动切换到对应结果页，无需上下翻找。")
    return selected_page


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


def activate_demo_source() -> None:
    """按钮回调：在下一次 rerun 前切换到真实缓存 Demo。"""
    st.session_state["data_source"] = "真实缓存 Demo"


def render_sidebar(
) -> tuple[
    pd.DataFrame,
    str,
    CollectionReport | None,
    AnalysisSnapshot | None,
]:
    """渲染输入区域并返回评论数据和用户的分析目标。"""
    st.sidebar.header("开始分析")
    source = st.sidebar.radio(
        "数据来源",
        [
            "内置示例数据",
            "真实缓存 Demo",
            "美国区 App Store 实时采集",
            "上传 CSV / JSON",
        ],
        key="data_source",
    )

    if source == "真实缓存 Demo":
        try:
            snapshot = load_snapshot(DEMO_SNAPSHOT_FILE)
        except AnalysisCacheError as error:
            st.sidebar.error(str(error))
            st.sidebar.info("请先完成一次真实美国区完整分析并保存为 Demo。")
            st.stop()
        if not snapshot.is_complete_demo:
            st.sidebar.error("缓存不是完整、可审计的美国区真实 Demo。")
            st.stop()
        report = CollectionReport(**snapshot.collection_report)
        st.sidebar.success(
            f"真实缓存：{report.app_name} · {len(snapshot.raw_reviews)} 条"
        )
        st.sidebar.caption(
            f"采集：{report.collected_at}｜模型：{snapshot.model_name}｜"
            f"快照：{snapshot.created_at}"
        )
        return (
            pd.DataFrame(snapshot.raw_reviews),
            snapshot.analysis_goal,
            report,
            snapshot,
        )

    goal = st.sidebar.text_area(
        "分析目标",
        value="了解用户最主要的不满，并找出优先改进方向",
        help="动态主题会结合这个目标，但不会使用写死的行业分类。",
        key="analysis_goal",
    )

    if source == "上传 CSV / JSON":
        uploaded_file = st.sidebar.file_uploader(
            "选择评论文件",
            type=["csv", "json"],
        )
        if uploaded_file is None:
            st.sidebar.info("尚未上传文件，暂时显示内置示例数据。")
            return load_sample_reviews(), goal, None, None
        return load_uploaded_reviews(uploaded_file), goal, None, None

    if source == "美国区 App Store 实时采集":
        app_url = st.sidebar.text_input(
            "App Store 链接",
            value=(
                "https://apps.apple.com/us/app/"
                "workout-for-women-home-gym/id839285684"
            ),
            help="可以粘贴中国区链接，但采集始终强制使用美国区 storefront。",
            key="app_store_url",
        )
        requested_count = st.sidebar.select_slider(
            "最多采集评论数",
            options=[50, 100, 200, 300, 500],
            value=100,
            key="requested_review_count",
        )
        live_key = analysis_fingerprint(
            [{"app_url": app_url, "requested_count": requested_count}],
            "us_app_store_collection",
        )
        if st.sidebar.button("采集美国区评论", type="primary"):
            st.session_state.pop("live_collection_records", None)
            st.session_state.pop("live_collection_report", None)
            st.session_state.pop("live_collection_key", None)
            st.session_state.pop("live_collection_error", None)
            try:
                with st.spinner("正在有限分页采集美国区公开评论……"):
                    result = collect_us_reviews(
                        app_url,
                        requested_review_count=requested_count,
                    )
            except AppStoreCollectionError as error:
                st.session_state["live_collection_error"] = str(error)
            else:
                st.session_state["live_collection_records"] = result.records
                st.session_state["live_collection_report"] = (
                    result.report.__dict__
                )
                st.session_state["live_collection_key"] = live_key

        saved_records = st.session_state.get("live_collection_records")
        saved_report = st.session_state.get("live_collection_report")
        saved_key = st.session_state.get("live_collection_key")
        if saved_records and saved_report and saved_key == live_key:
            report = CollectionReport(**saved_report)
            st.sidebar.success(
                f"已采集 {report.collected_review_count} 条美国区评论"
            )
            return pd.DataFrame(saved_records), goal, report, None
        if st.session_state.get("live_collection_error"):
            st.sidebar.error(st.session_state["live_collection_error"])
        st.sidebar.info(
            "点击采集后再开始分析。若实时接口失败，请切换到 CSV/JSON；系统不会补造评论。"
        )
        if DEMO_SNAPSHOT_FILE.exists():
            st.sidebar.button(
                "使用真实缓存 Demo",
                on_click=activate_demo_source,
                key="collection_use_demo",
            )
        st.stop()

    return load_sample_reviews(), goal, None, None


def render_collection_report(report: CollectionReport) -> None:
    """展示实时采集来源、数量、分页状态和限制。"""
    st.subheader("美国区实时采集报告")
    st.markdown(f"**App：{report.app_name}**")
    review_column, page_column, storefront_column = st.columns(3)
    review_column.metric(
        "采集评论", f"{report.collected_review_count}/{report.requested_review_count}"
    )
    page_column.metric(
        "成功页数", f"{report.pages_succeeded}/{report.pages_attempted}"
    )
    storefront_column.metric("Storefront", report.storefront.upper())
    st.caption(
        f"App ID：{report.app_id}；采集时间（UTC）：{report.collected_at}；"
        f"跨页重复移除：{report.duplicates_removed}；"
        f"格式异常移除：{report.malformed_removed}。"
    )
    st.markdown(f"美国区规范链接：[{report.canonical_url}]({report.canonical_url})")
    if report.empty_pages:
        st.info("本次公开 Feed 空页：" + "、".join(map(str, report.empty_pages)))
    for limitation in report.limitations:
        st.warning(limitation)
    with st.expander("查看本次实际请求的公开 Feed URL"):
        for source_url in report.source_urls:
            st.code(source_url, language=None)


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


def planning_input_fingerprint(
    finding_result: FindingGenerationResult, finding_fingerprint: str
) -> str:
    """标识 PRD 的上游输入，避免 Finding 重跑后显示旧规划。"""
    serialized = json.dumps(
        {
            "finding_fingerprint": finding_fingerprint,
            "finding_result": finding_result.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def test_input_fingerprint(
    plan_result: ProductPlanResult, planning_fingerprint: str
) -> str:
    """标识测试阶段上游输入，避免 PRD 重跑后显示旧用例。"""
    serialized = json.dumps(
        {
            "planning_fingerprint": planning_fingerprint,
            "plan_result": plan_result.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _snapshot_records(dataframe: pd.DataFrame) -> list[dict]:
    """把 Pandas 值转换为稳定、可 JSON 序列化的快照记录。"""
    return json.loads(dataframe.to_json(orient="records", date_format="iso"))


def _current_model_name() -> str:
    """只记录模型名称，不读取或保存 API Key。"""
    try:
        return ModelConfig.from_env().model
    except ModelConfigError:
        return "not-configured"


def _source_type(
    raw_reviews: pd.DataFrame, collection_report: CollectionReport | None
) -> str:
    if collection_report is not None:
        return "app_store_us"
    sources = set(raw_reviews.get("source", pd.Series(dtype=str)).dropna())
    if sources and sources == {"illustrative_sample"}:
        return "illustrative_sample"
    return "uploaded_file"


def build_current_snapshot(
    raw_reviews: pd.DataFrame,
    analysis_goal: str,
    current_fingerprint: str,
    cleaning_report: CleaningReport,
    collection_report: CollectionReport | None,
) -> AnalysisSnapshot:
    """把当前 session 中通过质量门的阶段结果整理为检查点。"""
    return create_snapshot(
        source_type=_source_type(raw_reviews, collection_report),
        analysis_goal=analysis_goal,
        analysis_fingerprint=current_fingerprint,
        model_name=_current_model_name(),
        raw_reviews=_snapshot_records(raw_reviews),
        cleaning_report=asdict(cleaning_report),
        collection_report=(
            asdict(collection_report) if collection_report is not None else None
        ),
        topic_result=st.session_state.get("topic_result"),
        finding_result=st.session_state.get("finding_result"),
        planning_result=st.session_state.get("planning_result"),
        test_result=st.session_state.get("test_result"),
    )


def persist_current_checkpoint(
    raw_reviews: pd.DataFrame,
    analysis_goal: str,
    current_fingerprint: str,
    cleaning_report: CleaningReport,
    collection_report: CollectionReport | None,
    *,
    promote_demo: bool = False,
) -> AnalysisSnapshot | None:
    """保存最近成功阶段；完整真实运行可同时更新演示缓存。"""
    try:
        snapshot = build_current_snapshot(
            raw_reviews,
            analysis_goal,
            current_fingerprint,
            cleaning_report,
            collection_report,
        )
        save_snapshot(snapshot, RUNTIME_CHECKPOINT_FILE)
        if promote_demo and snapshot.is_complete_demo:
            promote_complete_demo(snapshot, DEMO_SNAPSHOT_FILE)
        return snapshot
    except (AnalysisCacheError, ValueError) as error:
        st.warning(f"分析成功，但本地检查点保存失败：{error}")
        return None


def restore_snapshot_state(
    snapshot: AnalysisSnapshot, current_fingerprint: str
) -> None:
    """重新计算每层指纹后恢复结果，禁止跨输入误用旧结果。"""
    if snapshot.analysis_fingerprint != current_fingerprint:
        raise AnalysisCacheError("检查点与当前评论或分析目标不一致。")
    for key in (
        "topic_result",
        "topic_fingerprint",
        "finding_result",
        "finding_fingerprint",
        "planning_result",
        "planning_fingerprint",
        "test_result",
        "test_fingerprint",
    ):
        st.session_state.pop(key, None)

    if snapshot.topic_result is None:
        return
    st.session_state["topic_result"] = snapshot.topic_result.model_dump(
        mode="json"
    )
    st.session_state["topic_fingerprint"] = current_fingerprint
    finding_fingerprint = finding_input_fingerprint(
        snapshot.topic_result, current_fingerprint
    )
    if snapshot.finding_result is None:
        return
    st.session_state["finding_result"] = snapshot.finding_result.model_dump(
        mode="json"
    )
    st.session_state["finding_fingerprint"] = finding_fingerprint
    planning_fingerprint = planning_input_fingerprint(
        snapshot.finding_result, finding_fingerprint
    )
    if snapshot.planning_result is None:
        return
    st.session_state["planning_result"] = snapshot.planning_result.model_dump(
        mode="json"
    )
    st.session_state["planning_fingerprint"] = planning_fingerprint
    test_fingerprint = test_input_fingerprint(
        snapshot.planning_result, planning_fingerprint
    )
    if snapshot.test_result is None:
        return
    st.session_state["test_result"] = snapshot.test_result.model_dump(mode="json")
    st.session_state["test_fingerprint"] = test_fingerprint


def render_failure_recovery(stage: str, current_fingerprint: str) -> None:
    """在失败位置提供同输入检查点恢复和真实 Demo 降级。"""
    stage_fields = {
        "topic": ("topic_result", "动态主题"),
        "finding": ("finding_result", "Evidence Finding"),
        "planning": ("planning_result", "版本规划与 PRD"),
        "test": ("test_result", "测试用例与追溯"),
    }
    field_name, label = stage_fields[stage]
    try:
        checkpoint = load_snapshot(RUNTIME_CHECKPOINT_FILE)
    except AnalysisCacheError:
        checkpoint = None
    if (
        checkpoint is not None
        and checkpoint.analysis_fingerprint == current_fingerprint
        and getattr(checkpoint, field_name) is not None
    ):
        if st.button(
            f"使用上次成功的{label}",
            key=f"recover_{stage}_checkpoint",
        ):
            restore_snapshot_state(checkpoint, current_fingerprint)
            st.rerun()
    if DEMO_SNAPSHOT_FILE.exists():
        st.button(
            "切换到真实缓存 Demo",
            on_click=activate_demo_source,
            key=f"recover_{stage}_demo",
        )


def render_sidebar_checkpoint_recovery(current_fingerprint: str) -> None:
    """始终可见的最近成功进度恢复入口。"""
    try:
        checkpoint = load_snapshot(RUNTIME_CHECKPOINT_FILE)
    except AnalysisCacheError:
        return
    if (
        checkpoint.analysis_fingerprint == current_fingerprint
        and checkpoint.completed_stage != "input"
    ):
        st.sidebar.divider()
        st.sidebar.caption(
            f"最近成功进度：{checkpoint.completed_stage} · {checkpoint.created_at}"
        )
        if st.sidebar.button("恢复上次成功进度", key="restore_last_progress"):
            restore_snapshot_state(checkpoint, current_fingerprint)
            st.rerun()


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
    for index, topic in enumerate(result.topics):
        topic_review_ids = {
            insight_by_id[insight_id].review_id
            for insight_id in topic.insight_ids
            if insight_id in insight_by_id
        }
        with st.expander(
            f"{topic.topic_id} · {topic.name}", expanded=index == 0
        ):
            render_editorial_chips(
                [
                    (f"{len(topic.insight_ids)} 条原子观点", index == 0),
                    (f"{len(topic_review_ids)} 条去重评论", False),
                    (f"{len(topic.representative_review_ids)} 条代表评论", False),
                ]
            )
            st.write(topic.description)
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

    with st.expander(f"查看全部 {len(result.insights)} 条 Atomic Insights"):
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
    st.subheader("证据质量 · Finding Quality")
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
    for index, finding in enumerate(result.findings):
        with st.expander(
            f"{finding.finding_id} · {finding.title}", expanded=index == 0
        ):
            severity_labels = {
                "high": "高严重度",
                "medium": "中严重度",
                "low": "低严重度",
            }
            confidence_labels = {
                "high": "高置信度",
                "medium": "中置信度",
                "low": "低置信度",
            }
            severity_label = severity_labels.get(
                str(finding.severity).lower(), str(finding.severity)
            )
            confidence_label = confidence_labels.get(
                str(finding.confidence).lower(), str(finding.confidence)
            )
            chips = (
                (severity_label, True),
                (confidence_label, False),
                (f"{len(set(finding.supporting_review_ids))} 条支持评论", False),
                (f"{len(set(finding.conflicting_review_ids))} 条冲突证据", False),
            )
            chip_markup = "".join(
                '<span class="rs-chip'
                + (' rs-chip--strong' if strong else '')
                + f'">{escape(label)}</span>'
                for label, strong in chips
            )
            st.markdown(
                f'<div class="rs-chip-row">{chip_markup}</div>',
                unsafe_allow_html=True,
            )
            st.write(finding.description)
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


def render_product_plan(
    result: ProductPlanResult,
    finding_result: FindingGenerationResult,
) -> None:
    """展示版本路线图、PRD、证据追溯和非承诺产品假设。"""
    covered_finding_ids = {
        finding_id
        for requirement in result.requirements
        for finding_id in requirement.source_finding_ids
    }
    handled_finding_ids = covered_finding_ids | {
        item.finding_id for item in result.deferred_findings
    }
    coverage = (
        len(handled_finding_ids) / len(finding_result.findings) * 100
        if finding_result.findings
        else 0
    )
    requirement_column, release_column, coverage_column, hypothesis_column = (
        st.columns(4)
    )
    requirement_column.metric("正式需求", len(result.requirements))
    release_column.metric("规划版本", len(result.releases))
    coverage_column.metric("Finding 处理率", f"{coverage:.0f}%")
    hypothesis_column.metric("产品假设", len(result.product_hypotheses))

    st.subheader(result.prd_title)
    st.markdown(
        f'<div class="rs-summary-panel">{escape(result.executive_summary)}</div>',
        unsafe_allow_html=True,
    )

    st.subheader("版本路线图")
    for index, release in enumerate(result.releases):
        with st.expander(
            f"{release.release} · {release.objective}", expanded=index == 0
        ):
            render_editorial_chips(
                [
                    (release.release, index == 0),
                    (f"{len(release.requirement_ids)} 条需求", False),
                    (f"{len(release.risks)} 项风险", False),
                ]
            )
            st.write(release.rationale)
            st.caption("包含需求：" + "、".join(release.requirement_ids))
            if release.risks:
                st.markdown("**风险**")
                for risk in release.risks:
                    st.markdown(f"- {risk}")

    st.subheader("PRD 需求")
    for index, requirement in enumerate(result.requirements):
        with st.expander(
            f"{requirement.requirement_id} · {requirement.title}",
            expanded=index == 0,
        ):
            render_editorial_chips(
                [
                    (requirement.priority, True),
                    (requirement.release, False),
                    (f"{len(requirement.source_finding_ids)} 个 Finding", False),
                    (f"{len(requirement.source_review_ids)} 条来源评论", False),
                ]
            )
            st.write(requirement.description)
            st.caption(
                "来源 Finding："
                + "、".join(requirement.source_finding_ids)
                + "；来源 Review："
                + "、".join(requirement.source_review_ids)
            )
            scope_column, excluded_column = st.columns(2)
            with scope_column:
                st.markdown("**范围内**")
                for item in requirement.in_scope:
                    st.markdown(f"- {item}")
            with excluded_column:
                st.markdown("**范围外**")
                if requirement.out_of_scope:
                    for item in requirement.out_of_scope:
                        st.markdown(f"- {item}")
                else:
                    st.caption("本次未补充额外范围外事项。")
            st.markdown("**验收标准**")
            for criterion in requirement.acceptance_criteria:
                st.markdown(f"- {criterion}")

    st.subheader("证据追溯矩阵")
    traceability_rows = [
        {
            "Finding": finding_id,
            "Requirement": requirement.requirement_id,
            "Release": requirement.release,
            "Priority": requirement.priority,
            "Source Reviews": "、".join(requirement.source_review_ids),
        }
        for requirement in result.requirements
        for finding_id in requirement.source_finding_ids
    ]
    st.dataframe(
        pd.DataFrame(traceability_rows), width="stretch", hide_index=True
    )
    st.caption("Review ID 和优先级均由 Python 从已验证 Finding 派生，不由模型填写。")

    if result.deferred_findings:
        st.subheader("本轮暂缓的 Finding")
        for item in result.deferred_findings:
            st.info(
                f"{item.finding_id}：{item.reason}\n\n下一步验证：{item.next_validation}"
            )

    if result.product_hypotheses:
        st.subheader("Product Hypotheses（不属于承诺需求）")
        st.warning("以下内容没有被当前评论证据支持，必须先验证，不能直接进入版本承诺。")
        for item in result.product_hypotheses:
            with st.expander(f"{item.hypothesis_id} · {item.title}"):
                st.write(item.rationale)
                st.caption("验证计划：" + item.validation_plan)

    if result.limitations:
        st.subheader("规划限制")
        for limitation in result.limitations:
            st.warning(limitation)


def render_test_result(
    result: TestGenerationResult,
    finding_result: FindingGenerationResult,
    plan_result: ProductPlanResult,
    review_records: list[dict],
) -> None:
    """展示测试用例、覆盖指标和完整 Review → TestCase 追溯链。"""
    valid_review_ids = {record["review_id"] for record in review_records}
    quality = calculate_traceability_quality(
        result, finding_result, plan_result, valid_review_ids
    )
    st.subheader("测试质量 · Test Quality")
    requirement_column, scenario_column, traceability_column, invalid_column = (
        st.columns(4)
    )
    requirement_column.metric(
        "Requirement Coverage", f"{quality.requirement_coverage:.0f}%"
    )
    scenario_column.metric(
        "Required Scenario Coverage",
        f"{quality.critical_scenario_coverage:.0f}%",
    )
    traceability_column.metric(
        "Review Traceability", f"{quality.review_traceability:.0f}%"
    )
    invalid_column.metric("Invalid References", quality.invalid_references)
    st.caption(
        f"覆盖需求 {quality.covered_requirement_count}/{quality.requirement_count}；"
        f"必需场景 {quality.covered_critical_scenarios}/"
        f"{quality.required_critical_scenarios}；"
        f"可追溯评论 {quality.traceable_review_count}/"
        f"{quality.referenced_review_count}。全部由 Python 复算。"
    )
    if quality.quality_gate_passed:
        st.success("Traceability Quality Gate：通过")
    else:
        st.error("Traceability Quality Gate：未通过，结果不得进入最终交付。")

    st.subheader("测试用例")
    for index, test_case in enumerate(result.test_cases):
        with st.expander(
            f"{test_case.test_case_id} · {test_case.title}",
            expanded=index == 0,
        ):
            render_editorial_chips(
                [
                    (test_case.priority, True),
                    (test_case.test_type, False),
                    (test_case.requirement_id, False),
                    (f"{len(test_case.source_review_ids)} 条来源评论", False),
                ]
            )
            st.caption("来源 Review：" + "、".join(test_case.source_review_ids))
            st.markdown("**前置条件**")
            if test_case.preconditions:
                for item in test_case.preconditions:
                    st.markdown(f"- {item}")
            else:
                st.caption("无额外前置条件。")
            st.markdown("**执行步骤**")
            for index, step in enumerate(test_case.steps, start=1):
                st.markdown(f"{index}. {step}")
            st.markdown("**预期结果**")
            for index, expected in enumerate(test_case.expected_results, start=1):
                st.markdown(f"{index}. {expected}")

    finding_ids_by_requirement = {
        requirement.requirement_id: requirement.source_finding_ids
        for requirement in plan_result.requirements
    }
    st.subheader("端到端追溯矩阵")
    rows = [
        {
            "Review": "、".join(test_case.source_review_ids),
            "Finding": "、".join(
                finding_ids_by_requirement[test_case.requirement_id]
            ),
            "Requirement": test_case.requirement_id,
            "Test Case": test_case.test_case_id,
            "Scenario": test_case.test_type,
            "Priority": test_case.priority,
        }
        for test_case in result.test_cases
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        "TestCase 的 Review、优先级和最终 ID 均由 Python 从已验证 Requirement 派生。"
    )

    if result.limitations:
        st.subheader("测试限制")
        for limitation in result.limitations:
            st.warning(limitation)


def main() -> None:
    st.set_page_config(
        page_title="ReviewScope AI",
        page_icon="🔎",
        layout="wide",
    )

    render_editorial_theme()
    render_back_to_top()
    st.title("ReviewScope AI")
    st.caption("把真实用户评论转化为可执行产品改进方案")

    try:
        (
            raw_reviews,
            analysis_goal,
            collection_report,
            loaded_snapshot,
        ) = render_sidebar()
    except (
        ValueError,
        json.JSONDecodeError,
        pd.errors.ParserError,
        AnalysisCacheError,
    ) as error:
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
    demo_mode = loaded_snapshot is not None
    if loaded_snapshot is not None:
        try:
            restore_snapshot_state(loaded_snapshot, current_fingerprint)
        except AnalysisCacheError as error:
            st.error(f"真实缓存无法恢复：{error}")
            st.stop()

    if demo_mode:
        st.sidebar.success("缓存演示：无需网络或模型调用")
    elif model_configured():
        if st.session_state.get("model_call_verified"):
            st.sidebar.success("模型调用：已验证")
        else:
            st.sidebar.info("模型配置：已读取（尚未验证调用）")
    else:
        st.sidebar.warning("模型配置：未完成（参照 .env.example）")

    if not demo_mode:
        render_sidebar_checkpoint_recovery(current_fingerprint)
    selected_page = render_page_navigation()

    render_editorial_status_strip(demo_mode, collection_report)
    average_rating = cleaned_reviews["rating"].mean()

    if st.session_state.get("top_page_navigation") != selected_page:
        st.session_state["top_page_navigation"] = selected_page
    st.markdown(
        """
        <style>
        .st-key-top_page_navigation_bar [data-testid="stRadio"] > div {
            gap: 0;
            border-bottom: 1px solid rgba(128, 128, 128, 0.25);
        }
        .st-key-top_page_navigation_bar [data-testid="stRadio"] label {
            padding: 0.65rem 0.75rem;
            margin: 0;
            border-bottom: 2px solid transparent;
            white-space: nowrap;
        }
        .st-key-top_page_navigation_bar [data-testid="stRadio"] label:has(input:checked) {
            color: #111217;
            border-bottom-color: #111217;
            font-weight: 700;
        }
        .st-key-top_page_navigation_bar [data-testid="stRadio"] label > div:first-child {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="top_page_navigation_bar"):
        st.radio(
            "页面导航",
            PAGE_SECTIONS,
            key="top_page_navigation",
            on_change=sync_top_page_selection,
            horizontal=True,
            label_visibility="collapsed",
        )

    if selected_page == "数据概览":
        if collection_report is not None:
            render_collection_report(collection_report)

        st.subheader("本次目标")
        st.markdown(
            f'<div class="rs-summary-panel">{escape(analysis_goal)}</div>',
            unsafe_allow_html=True,
        )
        metric_1, metric_2, metric_3, metric_4 = st.columns(4)
        metric_1.metric("原始评论", len(raw_reviews))
        metric_2.metric("有效评论", len(cleaned_reviews))
        metric_3.metric("清洗移除", cleaning_report.removed_count)
        metric_4.metric(
            "平均评分",
            f"{average_rating:.1f}" if pd.notna(average_rating) else "暂无",
        )

        st.subheader("分析结果概览")
        render_editorial_outcome_summary(len(cleaned_reviews))
        st.write("")
        rating_counts = (
            cleaned_reviews["rating"]
            .value_counts()
            .reindex([1, 2, 3, 4, 5], fill_value=0)
            .rename_axis("评分")
            .rename("评论数量")
        )
        rating_chart_data = rating_counts.reset_index()
        rating_chart = (
            alt.Chart(rating_chart_data)
            .mark_bar(color="#111217", cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X(
                    "评分:O",
                    title=None,
                    sort=[1, 2, 3, 4, 5],
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y("评论数量:Q", title=None),
                tooltip=[
                    alt.Tooltip("评分:O", title="评分"),
                    alt.Tooltip("评论数量:Q", title="评论数量"),
                ],
            )
            .properties(height=320, title="评分分布")
            .configure_title(
                anchor="start",
                color="#111217",
                fontSize=17,
                fontWeight=700,
                offset=18,
            )
            .configure_axis(
                gridColor="#eceef1",
                domain=False,
                tickColor="#dfe1e5",
                labelColor="#727782",
            )
            .configure_view(strokeWidth=0)
        )
        st.markdown(
            """
            <style>
            .st-key-rating_distribution_chart [data-testid="stElementToolbar"] {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        chart_column, pipeline_column = st.columns([1.1, 0.9], gap="large")
        with chart_column:
            with st.container(key="rating_distribution_chart"):
                st.altair_chart(rating_chart, use_container_width=True)
        with pipeline_column:
            render_editorial_pipeline()
        st.caption("图表和数量由 Python 计算；已关闭缩放、平移和图表工具栏。")

    if selected_page == "清洗过程":
        st.subheader("评论清洗过程")
        st.markdown(
            "清洗由确定性 Python 规则完成，不调用大模型。"
            "每条评论只会在首次命中的规则中计数，因此各步骤数量不会重复。"
        )
        raw_column, valid_column, retention_column, removed_column = st.columns(4)
        raw_column.metric("原始记录", len(raw_reviews))
        valid_column.metric("有效评论", len(cleaned_reviews))
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

    if selected_page == "评论数据":
        st.subheader("清洗后的评论")
        low_rating_count = int((cleaned_reviews["rating"] <= 2).sum())
        version_count = (
            cleaned_reviews["version"].dropna().nunique()
            if "version" in cleaned_reviews.columns
            else 0
        )
        review_column, rating_column, low_column, version_column = st.columns(4)
        review_column.metric("有效评论", len(cleaned_reviews))
        rating_column.metric(
            "平均评分",
            f"{average_rating:.1f}" if pd.notna(average_rating) else "暂无",
        )
        low_column.metric("1–2 星评论", low_rating_count)
        version_column.metric("涉及版本", version_count)
        st.caption("表格保留稳定 Review ID，供 Finding、PRD 和测试用例追溯。")
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

    if selected_page == "动态主题":
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

        if st.button(
            "开始动态主题分析",
            type="primary",
            disabled=demo_mode,
            on_click=keep_page_selected,
            args=("动态主题",),
        ):
            st.session_state.pop("topic_result", None)
            st.session_state.pop("topic_fingerprint", None)
            st.session_state.pop("finding_result", None)
            st.session_state.pop("finding_fingerprint", None)
            st.session_state.pop("planning_result", None)
            st.session_state.pop("planning_fingerprint", None)
            st.session_state.pop("test_result", None)
            st.session_state.pop("test_fingerprint", None)
            try:
                with st.spinner("正在提取 Atomic Insight 并聚合动态主题……"):
                    result = TopicDiscoveryService().discover(
                        prepared_reviews, analysis_goal
                    )
            except (ModelConfigError, TopicDiscoveryError) as error:
                st.session_state["model_call_verified"] = False
                st.error(str(error))
                st.info("主题阶段已停止，不会生成 Finding、PRD 或测试用例。")
                render_failure_recovery("topic", current_fingerprint)
            else:
                st.session_state["model_call_verified"] = True
                st.session_state["topic_result"] = result.model_dump(mode="json")
                st.session_state["topic_fingerprint"] = current_fingerprint
                persist_current_checkpoint(
                    raw_reviews,
                    analysis_goal,
                    current_fingerprint,
                    cleaning_report,
                    collection_report,
                )
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

    if selected_page == "Evidence Finding":
        st.subheader("阶段 3：证据发现")
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
            if st.button(
                "生成 Evidence Finding",
                type="primary",
                disabled=demo_mode,
                on_click=keep_page_selected,
                args=("Evidence Finding",),
            ):
                st.session_state.pop("finding_result", None)
                st.session_state.pop("finding_fingerprint", None)
                st.session_state.pop("planning_result", None)
                st.session_state.pop("planning_fingerprint", None)
                st.session_state.pop("test_result", None)
                st.session_state.pop("test_fingerprint", None)
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
                    render_failure_recovery("finding", current_fingerprint)
                else:
                    st.session_state["finding_result"] = (
                        finding_result.model_dump(mode="json")
                    )
                    st.session_state["finding_fingerprint"] = (
                        current_finding_fingerprint
                    )
                    persist_current_checkpoint(
                        raw_reviews,
                        analysis_goal,
                        current_fingerprint,
                        cleaning_report,
                        collection_report,
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

    if selected_page == "版本规划与 PRD":
        st.subheader("阶段 4：版本规划与 PRD")
        st.markdown(
            "模型负责草拟版本目标、需求范围和验收标准；Python 负责校验 Finding 覆盖、"
            "派生 Review 证据、计算优先级并生成最终 REQ ID。Discovery 不会进入正式需求。"
        )
        saved_topic_result = st.session_state.get("topic_result")
        saved_topic_fingerprint = st.session_state.get("topic_fingerprint")
        current_topic_result = None
        if saved_topic_result and saved_topic_fingerprint == current_fingerprint:
            current_topic_result = TopicDiscoveryResult.model_validate(
                saved_topic_result
            )

        current_finding_result = None
        current_finding_fingerprint = None
        saved_finding_result = st.session_state.get("finding_result")
        saved_finding_fingerprint = st.session_state.get("finding_fingerprint")
        if current_topic_result is not None:
            current_finding_fingerprint = finding_input_fingerprint(
                current_topic_result, current_fingerprint
            )
            if (
                saved_finding_result
                and saved_finding_fingerprint == current_finding_fingerprint
            ):
                current_finding_result = FindingGenerationResult.model_validate(
                    saved_finding_result
                )

        if current_topic_result is None or current_finding_result is None:
            st.info("请先依次完成动态主题和 Evidence Finding，PRD 不会绕过证据阶段生成。")
        elif not current_finding_result.findings:
            st.warning(
                "当前只有 Discovery，没有达到证据门槛的 Finding；系统不会强行生成正式 PRD。"
            )
        else:
            current_planning_fingerprint = planning_input_fingerprint(
                current_finding_result, current_finding_fingerprint
            )
            if st.button(
                "生成版本规划与 PRD",
                type="primary",
                disabled=demo_mode,
                on_click=keep_page_selected,
                args=("版本规划与 PRD",),
            ):
                st.session_state.pop("planning_result", None)
                st.session_state.pop("planning_fingerprint", None)
                st.session_state.pop("test_result", None)
                st.session_state.pop("test_fingerprint", None)
                try:
                    with st.spinner("正在草拟需求并执行 PRD 证据与覆盖质量门……"):
                        planning_result = ProductPlanningService().generate(
                            prepared_reviews,
                            current_topic_result,
                            current_finding_result,
                            analysis_goal,
                        )
                except (ModelConfigError, ProductPlanningError) as error:
                    st.error(str(error))
                    st.info("PRD 阶段已停止，不会生成没有可靠来源的版本承诺。")
                    render_failure_recovery("planning", current_fingerprint)
                else:
                    st.session_state["planning_result"] = (
                        planning_result.model_dump(mode="json")
                    )
                    st.session_state["planning_fingerprint"] = (
                        current_planning_fingerprint
                    )
                    persist_current_checkpoint(
                        raw_reviews,
                        analysis_goal,
                        current_fingerprint,
                        cleaning_report,
                        collection_report,
                    )
                    st.success("版本规划与 PRD 生成完成，Finding 覆盖和追溯校验通过。")

            saved_planning_result = st.session_state.get("planning_result")
            saved_planning_fingerprint = st.session_state.get(
                "planning_fingerprint"
            )
            if (
                saved_planning_result
                and saved_planning_fingerprint == current_planning_fingerprint
            ):
                render_product_plan(
                    ProductPlanResult.model_validate(saved_planning_result),
                    current_finding_result,
                )
            elif saved_planning_result:
                st.info("上游 Finding 已改变，请重新生成版本规划与 PRD。")

    if selected_page == "测试用例与追溯":
        st.subheader("阶段 5：测试用例与完整追溯检查")
        st.markdown(
            "模型负责草拟正常、异常和边界测试；Python 负责校验 Requirement、"
            "派生 Review 与优先级，并检查 Review → Finding → Requirement → TestCase。"
        )
        current_topic_result = None
        saved_topic_result = st.session_state.get("topic_result")
        if (
            saved_topic_result
            and st.session_state.get("topic_fingerprint") == current_fingerprint
        ):
            current_topic_result = TopicDiscoveryResult.model_validate(
                saved_topic_result
            )

        current_finding_result = None
        current_finding_fingerprint = None
        if current_topic_result is not None:
            current_finding_fingerprint = finding_input_fingerprint(
                current_topic_result, current_fingerprint
            )
            saved_finding_result = st.session_state.get("finding_result")
            if (
                saved_finding_result
                and st.session_state.get("finding_fingerprint")
                == current_finding_fingerprint
            ):
                current_finding_result = FindingGenerationResult.model_validate(
                    saved_finding_result
                )

        current_plan_result = None
        current_planning_fingerprint = None
        if current_finding_result is not None:
            current_planning_fingerprint = planning_input_fingerprint(
                current_finding_result, current_finding_fingerprint
            )
            saved_planning_result = st.session_state.get("planning_result")
            if (
                saved_planning_result
                and st.session_state.get("planning_fingerprint")
                == current_planning_fingerprint
            ):
                current_plan_result = ProductPlanResult.model_validate(
                    saved_planning_result
                )

        if current_finding_result is None or current_plan_result is None:
            st.info("请先完成 Evidence Finding 和版本规划与 PRD，测试不会绕过需求生成。")
        else:
            current_test_fingerprint = test_input_fingerprint(
                current_plan_result, current_planning_fingerprint
            )
            if st.button(
                "生成测试用例并检查完整追溯",
                type="primary",
                disabled=demo_mode,
                on_click=keep_page_selected,
                args=("测试用例与追溯",),
            ):
                st.session_state.pop("test_result", None)
                st.session_state.pop("test_fingerprint", None)
                try:
                    with st.spinner("正在草拟测试并执行端到端追溯质量门……"):
                        test_result = TestGenerationService().generate(
                            prepared_reviews,
                            current_finding_result,
                            current_plan_result,
                            analysis_goal,
                        )
                except (ModelConfigError, TestGenerationError) as error:
                    st.error(str(error))
                    st.info("测试阶段已停止，不会展示引用断裂或覆盖不足的测试结果。")
                    render_failure_recovery("test", current_fingerprint)
                else:
                    st.session_state["test_result"] = test_result.model_dump(
                        mode="json"
                    )
                    st.session_state["test_fingerprint"] = (
                        current_test_fingerprint
                    )
                    snapshot = persist_current_checkpoint(
                        raw_reviews,
                        analysis_goal,
                        current_fingerprint,
                        cleaning_report,
                        collection_report,
                        promote_demo=True,
                    )
                    if snapshot is not None and snapshot.is_complete_demo:
                        st.success(
                            "真实美国区完整结果已同步保存为离线 Demo 缓存。"
                        )
                    st.success("测试用例生成完成，端到端追溯质量门通过。")

            saved_test_result = st.session_state.get("test_result")
            saved_test_fingerprint = st.session_state.get("test_fingerprint")
            if (
                saved_test_result
                and saved_test_fingerprint == current_test_fingerprint
            ):
                render_test_result(
                    TestGenerationResult.model_validate(saved_test_result),
                    current_finding_result,
                    current_plan_result,
                    prepared_records,
                )
            elif saved_test_result:
                st.info("上游 PRD 已改变，请重新生成测试用例。")

    if selected_page == "工作流程":
        st.subheader("从评论到可执行产品方案")
        st.markdown(
            "语义理解由模型完成，统计、引用和质量门由 Python 复算。"
            "任一阶段失败都会停止下游生成，不会用无依据内容补齐结果。"
        )
        render_editorial_workflow()
        st.info("下一阶段：结果导出与新环境最终验收。")

    st.divider()
    st.caption(
        "当前版本已打通美国区真实评论 → Topic → Finding → Requirement → TestCase 核心闭环。"
    )


if __name__ == "__main__":
    main()
