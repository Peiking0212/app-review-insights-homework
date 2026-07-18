"""分批 Atomic Insight 提取与全量 Topic 聚合提示词。"""

from __future__ import annotations

import json
from collections.abc import Sequence

from src.schemas import AtomicInsight, Review


INSIGHT_EXTRACTION_SYSTEM_PROMPT = """
你是 App 评论研究员。当前步骤只从本批评论提取 Atomic Insight，不生成 Topic。

规则：
1. 每条 Insight 只表达一个具体方面和一种主要情绪。
2. 同一条评论可以包含多个独立问题，因此可以生成多条 Insight；不得重复改写同一含义。
3. review_id 必须原样引用本批输入 ID；不要生成 insight_id，它由 Python 全局分配。
4. 只有完全没有可用观点、离题或无法判断的评论才进入 other_review_ids。
5. 每条本批评论必须被处理：至少产生一个 Insight，或者进入 OTHER，不能同时出现。
6. 不使用预设行业分类，不生成 Topic、代表评论、Finding、需求、PRD 或测试用例。
7. 数据或语义限制写入 limitations，不得补写评论中没有的事实。
""".strip()


TOPIC_AGGREGATION_SYSTEM_PROMPT = """
你是 App 评论研究员。当前步骤只对全量已验证 Atomic Insight 统一聚合 Topic。

规则：
1. 禁止使用预设行业分类或写死主题；Topic 必须从本次全量 Insight 动态归纳。
2. 每条 Insight 必须且只能属于一个 Topic，不得遗漏或跨 Topic 重复。
3. insight_id 必须原样引用输入中的 ID，不得创造、修改或删除 Insight。
4. 语义重叠的观点应合并；差异明显的观点不得为了减少 Topic 数量强行合并。
5. Topic 名称和说明使用简洁中文，但不得改变评论原意。
6. candidate_id 使用 TOPIC-CAND-001 起的唯一 ID。
7. 不输出 representative_review_ids；代表评论由 Python 从 Topic 内 Insight 推导。
8. 不生成 Finding、需求、PRD、测试用例或改进建议。
9. 聚合限制写入 limitations，不得编造统计数字。
""".strip()


def build_insight_extraction_messages(
    reviews: Sequence[Review],
    analysis_goal: str,
    batch_index: int,
    batch_count: int,
) -> list[dict[str, str]]:
    """构造单个评论批次的 Atomic Insight 提取消息。"""
    payload = [
        {
            "review_id": review.review_id,
            "rating": review.rating,
            "title": review.title,
            "content": review.content,
        }
        for review in reviews
    ]
    user_prompt = (
        f"分析目标：{analysis_goal.strip() or '发现当前评论中的主要用户体验主题'}\n"
        f"当前批次：{batch_index}/{batch_count}\n\n"
        "请只提取本批评论的 Atomic Insight，并逐条完成 Insight/OTHER 归属：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": INSIGHT_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_topic_aggregation_messages(
    insights: Sequence[AtomicInsight], analysis_goal: str
) -> list[dict[str, str]]:
    """构造基于全量已验证 Insight 的统一 Topic 聚合消息。"""
    payload = [insight.model_dump(mode="json") for insight in insights]
    user_prompt = (
        f"分析目标：{analysis_goal.strip() or '发现当前评论中的主要用户体验主题'}\n\n"
        "请将以下全量 Atomic Insight 统一聚合为动态 Topic。"
        "输出前检查每个 INSIGHT-* 恰好出现一次：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": TOPIC_AGGREGATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
