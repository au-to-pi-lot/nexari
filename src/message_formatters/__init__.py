from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.message_formatters.irc import IRCMessageFormatter
from src.message_formatters.openai import OpenAIMessageFormatter
from src.types.message_formatter import BaseMessageFormatter

formatters = {
    "irc": IRCMessageFormatter,
    "openai": OpenAIMessageFormatter
}

def get_message_formatter(name: str, session: AsyncSession) -> Optional[BaseMessageFormatter]:
    formatter_class = formatters.get(name)
    return formatter_class(session) if formatter_class else None
