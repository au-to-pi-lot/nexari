import discord

from src.event_handlers.on_guild_join import on_guild_join
from src.event_handlers.on_message import on_message
from src.event_handlers.on_ready import on_ready


def register_event_handlers(client: discord.Client):
    event_handlers = [
        on_guild_join,
        on_message,
        on_ready
    ]

    for event_handler in event_handlers:
        client.event(event_handler)
