from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.message_formatters.irc import IRCMessageFormatter
from src.types.message_formatter import BaseMessageFormatter

formatters = {
    "irc": IRCMessageFormatter
}

def get_message_formatter(name: str, session: AsyncSession) -> Optional[BaseMessageFormatter]:
    return formatters.get(name, None)(session)
