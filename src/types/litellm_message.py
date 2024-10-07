from typing import Optional

from pydantic import BaseModel


class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """

    role: str
    content: str
    name: Optional[str]
    """Name identifying the message. Only supported by OpenAI APIs."""
