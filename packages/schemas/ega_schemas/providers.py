"""Model Provider configuration and interaction schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelProviderType(str, Enum):
    DUMMY = "dummy"
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ModelConfig(BaseModel):
    """Configuration for an LLM provider endpoint."""

    provider_type: ModelProviderType = ModelProviderType.DUMMY
    model_name: str = "default"
    api_key: Optional[str] = Field(default=None, repr=False)
    base_url: Optional[str] = None
    temperature: float = 0.1
    timeout_seconds: int = 60
    max_tokens: int = 4096


class ModelCallRequest(BaseModel):
    """Standardized prompt call payload."""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.1
    max_tokens: int = 4096
    json_mode: bool = True
    context: dict[str, Any] = Field(default_factory=dict)


class ModelCallResponse(BaseModel):
    """Standardized response from any model provider."""

    raw_text: str
    parsed_json: Optional[dict[str, Any]] = None
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_name: str = ""
    provider: str = ""
