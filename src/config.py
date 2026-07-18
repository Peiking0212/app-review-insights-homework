"""从本地环境变量读取模型配置，不保存或输出 API Key。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ModelConfigError(ValueError):
    """模型配置缺失或不合法。"""


@dataclass(frozen=True)
class ModelConfig:
    api_key: str
    model: str
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> "ModelConfig":
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None

        missing = []
        if not api_key:
            missing.append("OPENAI_API_KEY")
        if not model:
            missing.append("OPENAI_MODEL")
        if missing:
            raise ModelConfigError(
                "缺少模型配置："
                + "、".join(missing)
                + "。请复制 .env.example 为 .env 后填写。"
            )
        return cls(api_key=api_key, model=model, base_url=base_url)


def model_configured() -> bool:
    """仅返回配置是否齐全，不暴露密钥内容。"""
    try:
        ModelConfig.from_env()
    except ModelConfigError:
        return False
    return True
