import discord

from src.event_handlers.on_guild_channel_create import on_guild_channel_create
from src.event_handlers.on_guild_channel_delete import on_guild_channel_delete
from src.event_handlers.on_guild_channel_update import on_guild_channel_update
from src.event_handlers.on_guild_join import on_guild_join
from src.event_handlers.on_guild_remove import on_guild_remove
from src.event_handlers.on_guild_update import on_guild_update
from src.event_handlers.on_message import on_message
from src.event_handlers.on_ready import on_ready
from src.event_handlers.on_message_edit import on_message_edit
from src.event_handlers.on_message_delete import on_message_delete


def register_event_handlers(client: discord.Client):
    event_handlers = [
        on_guild_channel_create,
        on_guild_channel_delete,
        on_guild_channel_update,
        on_guild_join,
        on_guild_remove,
        on_guild_update,
        on_message,
        on_message_delete,
        on_message_edit,
        on_ready,
    ]

    for event_handler in event_handlers:
        client.event(event_handler)
