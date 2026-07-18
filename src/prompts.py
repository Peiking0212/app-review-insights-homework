"""动态主题发现使用的提示词。"""

from __future__ import annotations

import json
from collections.abc import Sequence

from src.schemas import Review


TOPIC_SYSTEM_PROMPT = """
你是 App 评论研究员。你只能根据本次输入评论提取观点和发现主题。

规则：
1. 禁止使用预设行业分类或写死的主题列表；主题必须由当前评论归纳产生。
2. 先提取 Atomic Insight：每条 Insight 只表达一个具体方面和一种主要情绪。
3. 再把语义相近的 Insight 聚合为 Topic；每条 Insight 必须且只能属于一个 Topic。
4. Topic 名称和说明使用简洁中文，但不得改变评论原意。
5. 所有 review_id 必须原样引用输入中的 ID，不得创造评论、数字或 ID。
6. 无有效产品体验信息、离题或无法判断的评论放入 other_review_ids，不强行归类。
7. representative_review_ids 只能从该 Topic 的 Insight 所引用评论中选择。
8. 如果数据太少、目标造成偏差或存在其他限制，写入 limitations。
9. 不生成 Finding、需求、PRD、测试用例或改进建议。
""".strip()


def build_topic_messages(
    reviews: Sequence[Review], analysis_goal: str
) -> list[dict[str, str]]:
    """构造只包含必要评论字段的模型消息。"""
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
        f"分析目标：{analysis_goal.strip() or '发现当前评论中的主要用户体验主题'}\n\n"
        "请对下面的评论执行 Atomic Insight 提取和动态 Topic 聚合：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": TOPIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
