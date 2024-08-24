from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class SamplingConfig(BaseModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    repetition_penalty: Optional[float] = Field(default=None, ge=0.0)
    min_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_a: Optional[float] = Field(default=None, ge=0.0)


class LLMConfig(BaseModel):
    api_base: str
    llm_name: str
    api_key: str
    max_tokens: int
    sampling: SamplingConfig


class ChatConfig(BaseModel):
    context_length: int
    message_limit: int


class DiscordConfig(BaseModel):
    bot_token: str
    client_id: str


class WebhookConfig(BaseModel):
    name: str
    system_prompt: str
    llm: LLMConfig


class BotConfig(BaseModel):
    discord: DiscordConfig
    chat: ChatConfig
    webhooks: List[WebhookConfig]


class Config(BaseModel):
    bot: BotConfig


with open('config.yml', 'r') as config_file:
    config_dict = yaml.safe_load(config_file)
    config = Config(**config_dict)
