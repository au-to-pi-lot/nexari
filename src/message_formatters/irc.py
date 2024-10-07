import re
from itertools import chain
from typing import Optional

import discord
from discord import NotFound
from regex import regex

from src.db.models import Message
from src.services.channel import ChannelService
from src.services.discord_client import bot
from src.services.message import MessageService
from src.types.litellm_message import LiteLLMMessage
from src.types.message_formatter import ComboMessageFormatter, ParseResponse


class IRCMessageFormatter(ComboMessageFormatter):
    async def format_instruct(
            self,
            messages: list[Message],
            system_prompt: Optional[str],
            webhook: Optional[discord.Webhook],
    ) -> list[LiteLLMMessage]:
        message_service = MessageService(self.session)

        formatted_messages: list[LiteLLMMessage] = []
        if system_prompt is not None:
            formatted_messages.append(
                LiteLLMMessage(role="system", content=system_prompt)
            )
        for message in messages:
            if not message.content:
                continue

            matches = re.finditer(r"<@(?P<user_id>\d+)>", message.content)
            message_replaced_mentions = message.content
            for match in matches:
                user_id = match.group("user_id")
                try:
                    user = await bot.fetch_user(user_id)
                    message_replaced_mentions = message_replaced_mentions.replace(
                        f"<@{user_id}>", f"@{user.name}"
                    )
                except NotFound:
                    continue

            username = await message_service.author_name(message)

            if message.webhook_id:
                try:
                    msg_webhook = await bot.fetch_webhook(message.webhook_id)
                except NotFound as e:
                    continue
                role = (
                    "assistant"
                    if webhook is not None and msg_webhook.id == webhook.id
                    else "user"
                )
            else:
                role = "user"

            content = f"<{username}> {message.content}"
            formatted_messages.append(LiteLLMMessage(role=role, content=content))

        return formatted_messages

    async def format_simulator(
        self,
        messages: list[Message],
        system_prompt: Optional[str],
        webhook: Optional[discord.Webhook],
        users_in_channel: list[str] = None,
        force_response_from_user: Optional[str] = None,
    ) -> str:
        if users_in_channel is None:
            users_in_channel = []

        channel_service = ChannelService(session=self.session)
        channel = await channel_service.get(messages[0].channel_id)

        system_prompt_messages = [system_prompt] if system_prompt is not None else []
        channel_begin_messages = (
            [f"* Joined channel #{channel.name}"] if channel else []
        )
        user_join_messages = (f"* {user} joined" for user in users_in_channel)
        formatted_messages = await self.format_instruct(
            messages, None, webhook
        )

        # separate messages by 3 line breaks; messages should only contain 2 line breaks in a row
        prompt = (
            "\n\n\n".join(
                chain(
                    system_prompt_messages,
                    channel_begin_messages,
                    user_join_messages,
                    (message.content for message in formatted_messages),
                )
            )
            + "\n\n\n"
            + (
                f"<{force_response_from_user}>"
                if force_response_from_user is not None
                else ""
            )
        )
        return prompt


    async def parse_messages(self, response: str) -> ParseResponse:
        # Process the response line by line
        lines = response.split("\n")
        processed_lines = []
        active_username = None

        for line in lines:
            # Match multiple usernames at the start of the line
            match = regex.match(r"^(<[^>]+>\s*)+(?P<message>.*)$", line)
            if match:
                # Extract the first username without angle brackets
                first_username = regex.search(r"<([^>]+)>", match.group(0)).group(1)

                if active_username is None:
                    active_username = first_username

                if first_username != active_username:
                    # Stop processing if a different username is encountered
                    break

                processed_lines.append(match.group("message"))
            else:
                processed_lines.append(line)

        message = "\n".join(processed_lines)
        messages_to_send = IRCMessageFormatter.break_messages(message)

        return ParseResponse(
            complete_message=message,
            split_messages=messages_to_send,
            username=active_username,
        )

    async def parse_next_user(self, response: str, last_speaker: str) -> str:
        matches = regex.finditer(
            r"^<(?P<username>[^>]+)>",
            response,
            flags=re.MULTILINE,
        )
        usernames = [match.group("username") for match in matches]
        # Find the first username that's different from the last speaker
        next_speaker = next(
            (username for username in usernames if username != last_speaker), None
        )
        return next_speaker
