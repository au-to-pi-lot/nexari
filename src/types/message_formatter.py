from abc import ABC, abstractmethod
from typing import List

import discord
from litellm import ModelResponse

from src.types.litellm_message import LiteLLMMessage


class MessageFormatter(ABC):
    @abstractmethod
    def format(self, messages: List[discord.Message]) -> List[LiteLLMMessage]:
        """
        Format a list of Discord messages into a list of LiteLLMMessages.

        Args:
            messages (List[discord.Message]): The list of Discord messages to format.

        Returns:
            List[LiteLLMMessage]: The formatted list of LiteLLMMessages.
        """
        pass

    @abstractmethod
    def parse(self, response: ModelResponse) -> List[str]:
        """
        Parse a ModelResponse into a list of strings.

        Args:
            response (ModelResponse): The ModelResponse to parse.

        Returns:
            List[str]: The parsed list of strings.
        """
        pass
