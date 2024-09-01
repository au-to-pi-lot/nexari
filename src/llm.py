import logging
import textwrap
from datetime import datetime
from itertools import cycle, groupby
from typing import List, Literal, Union, Iterable, Optional

import discord
from litellm import acompletion
from litellm.types.utils import ModelResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.const import DISCORD_MESSAGE_MAX_CHARS, ROOT_DIR
from src.db.engine import Session
from src.db.models import LLM, Webhook, Guild
from src.db.models.guild import Guild as GuildModel
from src.util import drop_both_ends

logger = logging.getLogger(__name__)


class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """
    role: str
    content: str

class LLMHandler:
    def __init__(self, llm: LLM):
        self.llm = llm

    @classmethod
    async def get_llm_handlers(cls, guild: Union[discord.Guild, GuildModel, int]) -> List["LLMHandler"]:
        guild_id = Guild.get_guild_id(guild)
        async with Session() as session:
            guild = await Guild.get(guild_id, options=[selectinload(Guild.llms)], session=session)
            if guild is None:
                raise ValueError(f"Guild {guild_id} does not exist")
            models = guild.llms
        return [cls(model) for model in models]

    @classmethod
    async def get_handler(cls, name: str, guild: Union[discord.Guild, GuildModel, int]) -> Optional["LLMHandler"]:
        guild_id = Guild.get_guild_id(guild)
        model = await LLM.get_by_name(name, guild_id)
        return cls(model) if model else None

    async def get_webhook(self, bot: discord.Client, channel: discord.TextChannel) -> discord.Webhook:
        async with Session() as session:
            query = select(Webhook).where(
                Webhook.channel_id == channel.id and Webhook.llm_id == self.llm.id)
            db_webhook = (await session.scalars(query)).one_or_none()

            if db_webhook:
                webhook = await discord.Webhook.partial(
                    id=db_webhook.id,
                    token=db_webhook.token,
                    client=bot
                ).fetch()
            else:
                avatar = None
                if self.llm.avatar:
                    avatar_path = ROOT_DIR / 'avatars' / self.llm.avatar
                    if avatar_path.exists():
                        with open(avatar_path, 'rb') as avatar_file:
                            avatar = avatar_file.read()

                webhook = await channel.create_webhook(name=self.llm.name, avatar=avatar)
                session.add(Webhook(
                    id=webhook.id,
                    token=webhook.token,
                    channel_id=channel.id,
                    llm_id=self.llm.id,
                ))
                await session.commit()

        return webhook

    async def get_webhooks(self) -> List[Webhook]:
        """
        Retrieve all webhooks currently attached to the LLM.

        Returns:
            List[Webhook]: A list of Webhook objects associated with this LLM.
        """
        async with Session() as session:
            query = select(Webhook).where(Webhook.llm_id == self.llm.id)
            result = await session.execute(query)
            return result.scalars().all()

    async def generate_raw_response(self, messages: List[LiteLLMMessage]) -> ModelResponse:
        try:
            sampling_config = {
                "temperature": self.llm.temperature,
                "top_p": self.llm.top_p,
                "top_k": self.llm.top_k,
                "frequency_penalty": self.llm.frequency_penalty,
                "presence_penalty": self.llm.presence_penalty,
                "repetition_penalty": self.llm.repetition_penalty,
                "min_p": self.llm.min_p,
                "top_a": self.llm.top_a,
            }
            response = await acompletion(
                model=self.llm.llm_name,
                messages=messages,
                max_tokens=self.llm.max_tokens,
                **{key: val for key, val in sampling_config.items() if val is not None},
                api_base=self.llm.api_base,
                api_key=self.llm.api_key,
                stop=["<|begin_metadata|>"],
            )
            return response
        except Exception as e:
            logger.exception(f"Error in generate_response: {str(e)}")
            raise

    def get_system_prompt(self, guild_name: str, channel_name: str) -> str:
        return f"""\
{self.llm.system_prompt}

You are: {self.llm.name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {guild_name}
Current Discord Channel: {channel_name}
"""

    @staticmethod
    def parse_llm_response(content: str) -> str:
        if "<|begin_metadata|>" in content:
            content = content.split("<|begin_metadata|>", 1)[0]
        return content.strip()

    async def fetch_message_history(self, bot: discord.Client, channel: Union[discord.TextChannel, discord.DMChannel]) -> List[
        LiteLLMMessage]:
        """
        Fetch message history from a Discord channel.

        Args:
            channel (Union[discord.TextChannel, discord.DMChannel]): The channel to fetch history from.
            bot (discord.Client): The current discord client instance.

        Returns:
            List[LiteLLMMessage]: A list of messages in LiteLLM format.
        """
        discord_history: Iterable[discord.Message] = reversed(
            [
                message
                async for message in channel.history(limit=self.llm.message_limit)
            ]
        )

        webhook = await self.get_webhook(bot, channel)

        # group adjacent messages from the same user
        # this saves some tokens on repeated metadata
        history = []
        for _, message_group in groupby(discord_history, lambda a: a.author):
            message_group = list(message_group)
            first_message = message_group[0]
            role: str = "assistant" if first_message.webhook_id and first_message.webhook_id == webhook.id else "user"
            msg_content = "\n\n".join((message.content for message in message_group))
            content = f"""\
{msg_content}
<|begin_metadata|>
Author: {first_message.author.display_name + ("" if first_message.author.bot else f" ({first_message.author.name})")}
Author ID: {first_message.author.id}
Sent at: {first_message.created_at}
<|end_metadata|>
"""

            history.append(LiteLLMMessage(role=role, content=content))

        return history

    async def get_response(self, message_history: List[LiteLLMMessage]) -> str:
        """
        Generate a LLM response and post it to a Discord channel using the appropriate webhook.

        Args:
            message_history (List[LiteLLMMessage]): The message history in the channel.

        Returns:
            str: The literal response as generated by the LLM.
        """
        response = await self.generate_raw_response(message_history)
        response_str = response.choices[0].message.content

        content = LLMHandler.parse_llm_response(response_str)

        logger.info(f"Response from {self.llm.name}: {content}")

        return response_str

    @staticmethod
    def break_messages(content: str) -> List[str]:
        """
        Break a long message into smaller chunks that fit within Discord's message limit.

        Args:
            content (str): The content to break into messages.

        Returns:
            List[str]: A list of message chunks.
        """

        class CharBlock(BaseModel):
            content: str
            block_type: Literal['text', 'code']

        char_blocks = (
            CharBlock(content=content, block_type=block_type)
            for content, block_type in zip(content.split("```"), cycle(["text", "code"]))
            if content
        )

        blocks = []
        for block in char_blocks:
            if block.block_type == "text":
                block.content = block.content.strip()
                if block:
                    blocks.append(block)
            else:
                blocks.append(block)

        messages = []
        for block in blocks:
            if block.block_type == "text":
                messages.extend(
                    [
                        nonempty_message
                        for paragraph in block.content.split("\n\n")
                        for message in textwrap.wrap(
                        paragraph,
                        width=DISCORD_MESSAGE_MAX_CHARS,
                        expand_tabs=False,
                        replace_whitespace=False
                    )
                        if (nonempty_message := message.strip())
                    ]
                )
            elif block.block_type == "code":
                lines = block.content.split("\n")

                potential_language_marker = None
                if lines[0] != "":
                    potential_language_marker = lines[0]
                    lines = lines[1:]

                lines = drop_both_ends(lambda ln: ln == "", lines)

                if not lines and potential_language_marker:
                    lines = [potential_language_marker]

                if lines:
                    message_lines = []
                    current_length = 0
                    for index, line in enumerate(lines):
                        if current_length + len(line) + len("```\n") + len(
                                "\n```"
                                ) + 1 <= DISCORD_MESSAGE_MAX_CHARS:
                            message_lines.append(line)
                            current_length += len(line) + 1  # plus one for newline
                        else:
                            messages.append(
                                "```\n"
                                + "\n".join(message_lines)
                                + "\n```"
                            )
                            message_lines = []
                            current_length = 0

                    if message_lines:
                        messages.append(
                            "```\n"
                            + "\n".join(message_lines)
                            + "\n```"
                        )
                else:  # empty code block
                    messages.append("```\n```")

        return messages


