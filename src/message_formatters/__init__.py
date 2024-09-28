from typing import Optional

from src.message_formatters.irc import IRCMessageFormatter
from src.types.message_formatter import MessageFormatter

formatters = {
    "irc": IRCMessageFormatter
}

def get_message_formatter(name: str) -> Optional[MessageFormatter]:
    return formatters.get(name, None)()