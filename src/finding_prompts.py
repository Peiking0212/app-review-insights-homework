"""Evidence Finding 阶段使用的提示词。"""

from __future__ import annotations

import json
from collections.abc import Sequence

from src.schemas import Review, TopicDiscoveryResult


FINDING_SYSTEM_PROMPT = """
你是证据审慎的 App 产品研究员。你只能根据输入的 Review、Atomic Insight 和 Topic 草拟具体用户问题。

规则：
1. Finding 必须描述具体用户问题，不得写解决方案、功能需求或 PRD。
2. supporting_insight_ids 只能引用与问题直接一致的 negative 或 mixed Atomic Insight。
3. conflicting_insight_ids 应引用同一问题下明确表达相反或正面体验的 positive 或 mixed Atomic Insight；没有冲突证据时返回空列表。
4. Insight ID 必须原样引用输入，不得创造 ID、评论、数量、比例或事实。Review ID 与 Topic ID 将由 Python 从 Insight 关系推导。
5. 不要输出支持数量和置信度；它们由 Python 根据去重 Review ID 计算。
6. 只有一条支持评论、主题主要为正面、语义不清或与分析目标关系弱时，放入 discovery_candidates，不要夸大为 Finding。
7. 每个 Topic 的 Insight 必须至少被一个 Finding Candidate 或 Discovery Candidate 引用，不得静默遗漏 Topic。
8. 每个 Insight ID 在全部 candidates 和 discovery_candidates 中最多出现一次，包括 supporting_insight_ids、conflicting_insight_ids 和 discovery 的 insight_ids。
9. 如果一个 Insight 看起来能支持多个候选问题，必须合并语义重叠的问题，或只分配给最匹配的一个候选；不得复制同一 Insight 来提高多个问题的证据量。
10. severity 只表达问题一旦发生的用户影响，不代表出现频率。
11. 数据偏差、样本限制和无法判断的内容写入 limitations。
12. 不生成版本规划、优先级、需求、PRD 或测试用例。
""".strip()


def build_finding_messages(
    reviews: Sequence[Review],
    topic_result: TopicDiscoveryResult,
    analysis_goal: str,
) -> list[dict[str, str]]:
    """构造带完整证据文本、Insight 与 Topic 关系的模型消息。"""
    payload = {
        "analysis_goal": analysis_goal.strip()
        or "发现有证据支持的主要用户问题",
        "reviews": [
            {
                "review_id": review.review_id,
                "rating": review.rating,
                "title": review.title,
                "content": review.content,
            }
            for review in reviews
        ],
        "insights": [
            insight.model_dump(mode="json") for insight in topic_result.insights
        ],
        "topics": [topic.model_dump(mode="json") for topic in topic_result.topics],
        "topic_stage_limitations": topic_result.limitations,
    }
    return [
        {"role": "system", "content": FINDING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "请生成 Evidence Finding 候选与 Discovery 候选：\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n\n输出前必须执行以下硬性自检：\n"
            + "1. 汇总 candidates 的 supporting/conflicting 和 discovery_candidates 的全部 Insight ID。\n"
            + "2. 每个 Insight ID 在汇总结果中最多出现一次。\n"
            + "3. conflicting_insight_ids 已经算作 Topic 被覆盖，不得再把同一 Insight 放入 Discovery。\n"
            + "4. 如果发现重复，合并重叠候选或只保留最匹配的分配后再输出。",
        },
    ]
