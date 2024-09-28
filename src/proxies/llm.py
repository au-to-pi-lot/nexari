import asyncio
import logging
import os
import shutil
from collections import defaultdict
from typing import List, Optional, Self, TYPE_CHECKING, Any

import aiohttp
import discord
import sqlalchemy
from litellm import acompletion
from litellm.types.utils import ModelResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src import message_formatters
from src.const import AVATAR_DIR
from src.db.models import LLM, Webhook
from src.db.models.llm import LLMCreate
from src.message_formatters import get_message_formatter
from src.proxies import WebhookProxy
from src.proxies.message import MessageProxy
from src.services.db import Session
from src.services.discord_client import bot
from src.types.litellm_message import LiteLLMMessage
from src.types.message_formatter import MessageFormatter
from src.types.proxy import BaseProxy

if TYPE_CHECKING:
    from src.proxies import ChannelProxy

logger = logging.getLogger(__name__)


channel_locks: defaultdict[int, asyncio.Lock] = defaultdict(
    asyncio.Lock
)  # keyed by channel ID


class LLMProxy(BaseProxy[None, LLM]):
    def __init__(self, llm: LLM) -> None:
        super().__init__(None, llm)

    @classmethod
    async def get(cls, identifier: int) -> Optional[Self]:
        async with Session() as session:
            llm = (
                await session.scalars(select(LLM).filter(LLM.id == identifier))
            ).one_or_none()
            if llm is None:
                return None
            return cls(llm)

    @classmethod
    async def get_all(cls, guild_id: int) -> List[Self]:
        """
        Retrieve all LLMs for a given guild.

        Args:
            guild_id (int): The ID of the guild to retrieve LLMs for.

        Returns:
            List[Self]: A list of LLMProxy instances for all LLMs in the guild.
        """
        async with Session() as session:
            stmt = select(LLM).where(LLM.guild_id == guild_id)
            result = await session.execute(stmt)
            llms = result.scalars().all()
            return [cls(llm) for llm in llms]

    @classmethod
    async def get_by_name(cls, name: str, guild_id: int) -> Optional[Self]:
        async with Session() as session:
            llm = (
                await session.scalars(
                    select(LLM).filter(LLM.name == name, LLM.guild_id == guild_id)
                )
            ).one_or_none()
            if llm is None:
                return None
            return cls(llm)

    @property
    def id(self) -> int:
        return self._db_obj.id

    @property
    def name(self) -> str:
        return self._db_obj.name

    @property
    def api_base(self):
        return self._db_obj.api_base

    @property
    def llm_name(self) -> str:
        return self._db_obj.llm_name

    @property
    def api_key(self) -> str:
        return self._db_obj.api_key

    @property
    def avatar(self) -> Optional[str]:
        return self._db_obj.avatar

    @property
    def system_prompt(self) -> Optional[str]:
        return self._db_obj.system_prompt

    @property
    def max_tokens(self) -> int:
        return self._db_obj.max_tokens

    @property
    def message_limit(self) -> int:
        return self._db_obj.message_limit

    @property
    def instruct_tuned(self) -> bool:
        return self._db_obj.instruct_tuned

    @property
    def message_formatter(self) -> Optional[MessageFormatter]:
        return get_message_formatter(self._db_obj.message_formatter)

    @property
    def temperature(self) -> float:
        return self._db_obj.temperature

    @classmethod
    async def create(cls, llm_data: LLMCreate, *, session: AsyncSession = None) -> Self:
        async def _create(s: AsyncSession):
            db_llm = LLM(**llm_data.dict())
            s.add(db_llm)
            await s.commit()
            await s.refresh(db_llm)
            return cls(db_llm)

        if session is None:
            async with Session() as session:
                return await _create(session)
        else:
            return await _create(session)

    async def save(self) -> None:
        async with Session() as session:
            session.add(self._db_obj)
            await session.commit()

    async def edit(self, **kwargs):
        columns = LLM.__table__.columns.keys()
        old_name = self.name
        for key, value in kwargs.items():
            if key == "name" and value != old_name:
                # If the name has changed, update all associated webhooks
                webhooks = await self.get_webhooks()
                for webhook in webhooks:
                    try:
                        await webhook.edit(name=kwargs["name"])
                    except Exception as e:
                        logger.error(f"Failed to update webhook {webhook.id} name: {e}")
                        raise
            elif key == "message_formatter":
                if value not in message_formatters.formatters:
                    raise ValueError(f"Invalid message formatter: {value}")

            if key in columns:
                setattr(self._db_obj, key, value)

        await self.save()

    async def get_webhook(self, channel_id: int) -> WebhookProxy:
        from src.proxies import ChannelProxy

        channel = await ChannelProxy.get(channel_id)

        async with channel_locks[channel_id]:
            async with Session() as session:
                query = select(Webhook).where(
                    Webhook.channel_id == channel_id, Webhook.llm_id == self.id
                )
                db_webhook = (await session.scalars(query)).one_or_none()

                if db_webhook:
                    webhook = await bot.fetch_webhook(db_webhook.id)
                else:
                    avatar = None
                    if self.avatar:
                        avatar_path = AVATAR_DIR / self.avatar
                        if avatar_path.exists():
                            with open(avatar_path, "rb") as avatar_file:
                                avatar = avatar_file.read()

                    webhook = await channel.create_webhook(
                        name=self.name, avatar=avatar
                    )
                    db_webhook = Webhook(
                        id=webhook.id,
                        token=webhook.token,
                        channel_id=channel.id,
                        llm_id=self.id,
                    )
                    session.add(db_webhook)
                    await session.commit()
                    await session.refresh(db_webhook)

        return WebhookProxy(db_webhook=db_webhook, discord_webhook=webhook)

    @staticmethod
    async def cleanup_duplicate_webhooks():
        async with Session() as session:
            # Find duplicates
            duplicates = await session.execute(
                select(Webhook.channel_id, Webhook.llm_id)
                .group_by(Webhook.channel_id, Webhook.llm_id)
                .having(sqlalchemy.func.count() > 1)
            )

            for channel_id, llm_id in duplicates:
                webhooks = await session.execute(
                    select(Webhook)
                    .where(Webhook.channel_id == channel_id, Webhook.llm_id == llm_id)
                    .order_by(Webhook.id)
                )
                webhooks = webhooks.scalars().all()

                # Keep the first one, delete the rest
                for webhook in webhooks[1:]:
                    await session.delete(webhook)
                    # Also delete the Discord webhook if it exists
                    try:
                        discord_webhook = await bot.fetch_webhook(webhook.id)
                        await discord_webhook.delete()
                    except discord.NotFound:
                        pass

            await session.commit()

    async def get_webhooks(self) -> List[WebhookProxy]:
        """
        Fetch the list of webhooks associated with the LLM.

        Args:
            bot (commands.Bot): The Discord bot instance.

        Returns:
            List[discord.Webhook]: The list of webhooks associated with the LLM.
        """
        webhooks = []
        async with Session() as session:
            llm = (
                await session.scalars(
                    select(LLM)
                    .options(selectinload(LLM.webhooks))
                    .where(LLM.id == self.id)
                )
            ).one_or_none()
            if llm:
                for db_webhook in llm.webhooks:
                    try:
                        discord_webhook = await bot.fetch_webhook(db_webhook.id)
                        webhooks.append(
                            WebhookProxy(
                                discord_webhook=discord_webhook, db_webhook=db_webhook
                            )
                        )
                    except Exception as e:
                        logger.error(
                            f"Error fetching webhook {db_webhook.id} for LLM {self.name}: {e}"
                        )
            else:
                logger.error(f"Error fetching LLM {self.name}")

        return webhooks

    async def generate_instruct_response(
        self, messages: List[LiteLLMMessage]
    ) -> ModelResponse:
        try:
            sampling_config = {
                "temperature": self._db_obj.temperature,
                "top_p": self._db_obj.top_p,
                "top_k": self._db_obj.top_k,
                "frequency_penalty": self._db_obj.frequency_penalty,
                "presence_penalty": self._db_obj.presence_penalty,
                "repetition_penalty": self._db_obj.repetition_penalty,
                "min_p": self._db_obj.min_p,
                "top_a": self._db_obj.top_a,
            }
            response = await acompletion(
                model=self._db_obj.llm_name,
                messages=messages,
                max_tokens=self.max_tokens,
                **{key: val for key, val in sampling_config.items() if val is not None},
                api_base=self._db_obj.api_base,
                api_key=self._db_obj.api_key,
                stop=[],
            )
            return response
        except Exception as e:
            logger.exception(f"Error in generate_response: {str(e)}")
            raise

    async def generate_simulator_response(self, prompt: str, stop_words: list[str] = None) -> dict[str, Any]:
        if stop_words is None:
            stop_words = []

        url = f"{self.api_base}/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Nexari/0.1.0"
        }
        data = {
            "model": self.llm_name,
            "prompt": prompt,
            "max_tokens": self.max_tokens,
            "stop": stop_words
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                for attempt in range(3):
                    if response.status == 200:
                        try:
                            result = await response.json()
                            if result:
                                return result
                            else:
                                logger.warning(f"Empty simulator response received. Attempt {attempt + 1} of 3.")
                                logger.warning(await response.text())
                        except aiohttp.client_exceptions.ClientPayloadError as e:
                            logger.warning(f"ClientPayloadError occurred: {e}. Attempt {attempt + 1} of 3.")

                        if attempt < 2:
                            continue
                    else:
                        raise Exception(f"Error {response.status}: {await response.text()}")

                raise ValueError("Failed to get a valid response after 3 attempts")

    async def mentioned_in_message(self, message: MessageProxy) -> bool:
        mentioned = f"@{self.name.lower()}" in message.content.lower()
        return mentioned

    async def delete(self) -> None:
        """
        Delete the LLM from the database.
        """
        async with Session() as session:
            await session.delete(self._db_obj)
            await session.commit()
        self._db_obj = None

    async def copy(self, new_name: str, *, session: AsyncSession = None) -> "LLMProxy":
        """
        Create a new instance of LLM with all the same values as the source instance, but with a different name.

        Args:
            new_name (str): The name for the new LLM instance.

        Returns:
            LLMProxy: A new LLMProxy instance with copied values and the new name.
        """
        new_llm_data = {
            "name": new_name,
            "guild_id": self._db_obj.guild_id,
            "api_base": self.api_base,
            "llm_name": self.llm_name,
            "api_key": self.api_key,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "context_length": self._db_obj.context_length,
            "message_limit": self._db_obj.message_limit,
            "instruct_tuned": self.instruct_tuned,
            "enabled": self._db_obj.enabled,
            "message_formatter": self._db_obj.message_formatter,
            "temperature": self._db_obj.temperature,
            "top_p": self._db_obj.top_p,
            "top_k": self._db_obj.top_k,
            "frequency_penalty": self._db_obj.frequency_penalty,
            "presence_penalty": self._db_obj.presence_penalty,
            "repetition_penalty": self._db_obj.repetition_penalty,
            "min_p": self._db_obj.min_p,
            "top_a": self._db_obj.top_a,
        }

        # Copy the avatar file if it exists
        if self.avatar:
            source_avatar_path = AVATAR_DIR / self.avatar
            if os.path.exists(source_avatar_path):
                file_extension = os.path.splitext(self.avatar)[1]
                new_avatar_filename = f"{new_name}{file_extension}"
                new_avatar_path = AVATAR_DIR / new_avatar_filename
                shutil.copy2(source_avatar_path, new_avatar_path)
                new_llm_data["avatar"] = new_avatar_filename
            else:
                logger.warning(
                    f"Avatar file {source_avatar_path} not found. New LLM will not have an avatar."
                )

        async def _copy(s: AsyncSession):
            new_llm = await self.create(LLMCreate(**new_llm_data), session=s)
            return new_llm

        if not session:
            async with Session() as session:
                return await _copy(session)
        else:
            return await _copy(session)

    async def set_avatar(self, avatar: bytes, filename: str) -> None:
        """
        Set the avatar for the LLM and all its associated webhooks.

        Args:
            avatar (bytes): The avatar image data.
            filename (str): The filename for the avatar.

        Raises:
            ValueError: If the avatar file is too large.
        """

        if len(avatar) > 1024 * 1024 * 8:  # 8 MB limit
            raise ValueError("The image file is too large. Maximum size is 8 MB.")

        avatar_path = AVATAR_DIR / filename

        # Save the avatar file
        with open(avatar_path, "wb") as f:
            f.write(avatar)

        # Update the LLM's avatar in the database
        await self.edit(avatar=filename)

        # Update the avatar for all associated webhooks
        webhooks = await self.get_webhooks()
        for webhook in webhooks:
            try:
                await webhook.set_avatar(avatar=avatar)
            except Exception as e:
                logger.error(f"Failed to update avatar for webhook {webhook.id}: {e}")

        logger.info(f"Avatar set for LLM {self.name} and its webhooks: {filename}")

    async def respond(self, channel: "ChannelProxy") -> None:
        """
        Generate a response and post it in the given channel.

        Args:
            channel (ChannelProxy): The channel to post the response in.
        """
        history = list(reversed(await channel.history(limit=self.message_limit)))
        webhook = await self.get_webhook(channel.id)
        guild = await channel.get_guild()

        try:
            # Generate the response
            if self.instruct_tuned:
                messages = await self.message_formatter.format_instruct(history, self.system_prompt, webhook)
                response = await self.generate_instruct_response(messages)
                response_str = response.choices[0].message.content
            else:
                llms_in_guild = await guild.get_llms()
                prompt = await self.message_formatter.format_simulator(history, self.system_prompt, webhook, channel, [llm.name for llm in llms_in_guild], self.name)
                response = await self.generate_simulator_response(prompt, ['\n\n\n'])
                response_str = response["choices"][0]["text"]

            logger.info(f"{self.name} (#{channel.name}): {response_str}")

            if response_str == "":
                logger.info(f"{self.name} declined to respond in channel {channel.id}")
                return

            parse_response = await self.message_formatter.parse_messages(response_str)
            response_messages = parse_response.split_messages
            response_username = parse_response.username

            if response_username is None:
                # If no usernames were found, assume it's from this LLM
                response_username = self.name

            if response_username == self.name:
                # If the message is from this LLM, send it
                for message in response_messages:
                    await webhook.send(message)
                logger.info(f"Msg in channel {channel.id} from {response_username}: {parse_response.complete_message}")
            else:
                # Otherwise, pass control to other LLM, if it exists
                other_llm = await LLMProxy.get_by_name(response_username, self._db_obj.guild_id)
                if other_llm:
                    logger.info(f"{self.name} passed to {other_llm.name}")
                    await other_llm.respond(channel)
                elif member := guild.get_member_named(response_username):
                    # Or, if it's a human's username, mention them
                    await webhook.send(f"<@{member.id}>")
                else:
                    # If no matching LLM or user found, send the message as is
                    for message in response_messages:
                        await webhook.send(message)
                    logger.warning(f"{self.name} sent a message with unknown username: {response_username}")

        except Exception as e:
            logger.exception(f"Error in respond method: {str(e)}")
            # Optionally, you could send an error message to the channel here
