"""阶段 4：版本规划与 PRD 的证据约束提示词。"""

from __future__ import annotations

import json
from collections.abc import Sequence

from src.finding_analysis import FindingQualityReport
from src.schemas import FindingGenerationResult, Review


def build_planning_messages(
    reviews: Sequence[Review],
    finding_result: FindingGenerationResult,
    analysis_goal: str,
    quality: FindingQualityReport,
) -> list[dict[str, str]]:
    """只把已通过质量门的 Finding 作为正式需求证据。"""
    review_by_id = {review.review_id: review for review in reviews}
    findings = []
    for finding in finding_result.findings:
        findings.append(
            {
                **finding.model_dump(mode="json"),
                "supporting_reviews": [
                    {
                        "review_id": review_id,
                        "rating": review_by_id[review_id].rating,
                        "content": review_by_id[review_id].content,
                    }
                    for review_id in finding.supporting_review_ids
                ],
                "support_count": len(set(finding.supporting_review_ids)),
                "conflict_count": len(set(finding.conflicting_review_ids)),
            }
        )

    payload = {
        "analysis_goal": analysis_goal,
        "groundedness": {
            "evidence_coverage": quality.evidence_coverage,
            "review_traceability": quality.review_traceability,
            "unsupported_claims": quality.unsupported_claims,
            "conflict_evidence": quality.conflict_evidence,
        },
        "eligible_findings": findings,
        "excluded_discovery": [
            item.model_dump(mode="json") for item in finding_result.discovery_items
        ],
        "upstream_limitations": finding_result.limitations,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是谨慎的产品经理。请把已验证 Finding 转成精简、可执行、可测试的"
                "版本规划与 PRD 草稿。不得补写输入中没有的用户事实、数量或评论 ID。\n"
                "硬性规则：\n"
                "1. 正式需求只能引用 eligible_findings 中真实存在的 FIND-* ID；"
                "excluded_discovery 证据不足，绝不能转成正式需求。\n"
                "2. 每个 eligible Finding 必须恰好二选一：被至少一个需求覆盖，或列入"
                " deferred_findings；同一 Finding 不能同时出现于两处。\n"
                "3. 根据证据实际需要生成 1-6 条需求、1-3 个版本，不得为了数量凑数。\n"
                "4. candidate_id 使用 REQC-001 起的唯一 ID。版本只引用这些 candidate_id，"
                "且每条候选需求恰好进入一个版本。\n"
                "5. 不要填写 Review ID、P0-P3 或最终 REQ ID；它们由 Python 从 Finding"
                "确定性推导。\n"
                "6. 每条需求必须说明 description、in_scope、out_of_scope 和可验证的"
                "acceptance_criteria；验收标准描述可观察结果，不编造技术实现。\n"
                "7. 无评论证据但值得探索的想法只能写进 product_hypotheses，使用 HYP-* ID，"
                "并提供验证计划；它不是承诺交付的需求。没有必要时返回空数组。\n"
                "8. 不生成测试用例。使用与输入一致的语言输出。"
            ),
        },
        {
            "role": "user",
            "content": "请基于以下已校验数据生成版本规划与 PRD 草稿：\n"
            + json.dumps(payload, ensure_ascii=False, indent=2),
        },
    ]
