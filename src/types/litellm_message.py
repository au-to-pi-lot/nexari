from pydantic import BaseModel


class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """

    role: str
    content: str
