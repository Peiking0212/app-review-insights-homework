"""阶段 5：测试用例生成的证据约束提示词。"""

from __future__ import annotations

import json
from collections.abc import Sequence

from src.schemas import ProductPlanResult, Review


def build_test_messages(
    reviews: Sequence[Review],
    plan_result: ProductPlanResult,
    analysis_goal: str,
) -> list[dict[str, str]]:
    """构造只允许引用已验证 Requirement 的测试生成消息。"""
    review_by_id = {review.review_id: review for review in reviews}
    payload = {
        "analysis_goal": analysis_goal,
        "requirements": [
            {
                **requirement.model_dump(mode="json"),
                "source_reviews": [
                    {
                        "review_id": review_id,
                        "rating": review_by_id[review_id].rating,
                        "content": review_by_id[review_id].content,
                    }
                    for review_id in requirement.source_review_ids
                ],
            }
            for requirement in plan_result.requirements
        ],
        "planning_limitations": plan_result.limitations,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是严谨的软件测试工程师。请根据已验证 Requirement 和验收标准草拟"
                "可执行测试场景，不得增加输入中没有的产品能力或业务规则。\n"
                "硬性规则：\n"
                "1. requirement_id 只能引用输入中真实存在的 REQ-*；不要填写 Review ID、"
                "优先级或最终 TC ID，它们由 Python 派生。\n"
                "2. 每条 Requirement 至少生成一个 normal 场景。\n"
                "3. 每条 P0/P1 Requirement 必须分别生成 normal、negative、boundary 三种场景；"
                "不要用一条测试冒充三种覆盖。\n"
                "4. candidate_id 使用 TCC-001 起的唯一 ID；scenario_type 只能是 normal、"
                "negative、boundary。\n"
                "5. 步骤必须是可执行动作，预期结果必须是可观察结果；不要写“功能正常”"
                "或“符合预期”这类无法验证的内容。\n"
                "6. 测试必须验证 Requirement 的范围与验收标准。out_of_scope 只能用于确认"
                "边界，不得把它变成新增功能。\n"
                "7. 如果输入缺少设备、接口或业务规则，写入 limitations，不得自行编造。\n"
                "8. 使用与输入一致的语言输出。"
            ),
        },
        {
            "role": "user",
            "content": "请基于以下已校验 PRD 草拟测试用例：\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n\n输出前请检查：所有 Requirement 至少有 normal；所有 P0/P1 同时有"
            + " normal、negative、boundary；没有未知 REQ ID。",
        },
    ]
