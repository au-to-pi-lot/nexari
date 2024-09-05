import logging
import os
import shutil
from datetime import datetime
from typing import List, Optional, Self, TYPE_CHECKING

import discord
from discord import NotFound
from discord.ext.commands import Bot
from litellm import acompletion
from litellm.types.utils import ModelResponse
from regex import regex
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.const import AVATAR_DIR
from src.db.models import LLM, Webhook
from src.db.models.llm import LLMCreate
from src.proxies import WebhookProxy
from src.proxies.message import MessageProxy
from src.services import svc
from src.types.litellm_message import LiteLLMMessage
from src.types.proxy import BaseProxy

if TYPE_CHECKING:
    from src.proxies import ChannelProxy

logger = logging.getLogger(__name__)


class LLMProxy(BaseProxy[None, LLM]):
    def __init__(self, llm: LLM) -> None:
        super().__init__(None, llm)

    @classmethod
    async def get(cls, identifier: int) -> Optional[Self]:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
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
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
        async with Session() as session:
            stmt = select(LLM).where(LLM.guild_id == guild_id)
            result = await session.execute(stmt)
            llms = result.scalars().all()
            return [cls(llm) for llm in llms]

    @classmethod
    async def get_by_name(cls, name: str, guild_id: int) -> Optional[Self]:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
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
    def name(self) -> str:
        return self._db_obj.name

    @property
    def llm_name(self) -> str:
        return self._db_obj.llm_name

    @classmethod
    async def create(cls, llm_data: LLMCreate, *, session: AsyncSession = None) -> Self:
        async def _create(s: AsyncSession):
            db_llm = LLM(**llm_data.dict())
            session.add(db_llm)
            await session.commit()
            await session.refresh(db_llm)
            return cls(db_llm)

        if session is None:
            Session: type[AsyncSession] = svc.get(type[AsyncSession])
            async with Session() as session:
                return await _create(session)
        else:
            return await _create(session)

    async def save(self) -> None:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
        async with Session() as session:
            session.add(self._db_obj)
            await session.commit()

    async def edit(self, **kwargs):
        columns = LLM.__table__.columns.keys()
        for key, value in kwargs.items():
            if key in columns:
                setattr(self._db_obj, key, value)
        await self.save()

    async def get_webhook(self, channel_id) -> WebhookProxy:
        from src.proxies import ChannelProxy

        Session: type[AsyncSession] = svc.get(type[AsyncSession])
        bot = svc.get(Bot)

        channel = await ChannelProxy.get(channel_id)

        async with Session() as session:
            query = select(Webhook).where(
                Webhook.channel_id == channel_id, Webhook.llm_id == self._db_obj.id
            )
            db_webhook = (await session.scalars(query)).one_or_none()

            if db_webhook:
                webhook = await bot.fetch_webhook(db_webhook.id)
            else:
                avatar = None
                if self._db_obj.avatar:
                    avatar_path = AVATAR_DIR / self._db_obj.avatar
                    if avatar_path.exists():
                        with open(avatar_path, "rb") as avatar_file:
                            avatar = avatar_file.read()

                webhook = await channel.create_webhook(
                    name=self._db_obj.name, avatar=avatar
                )
                db_webhook = Webhook(
                    id=webhook.id,
                    token=webhook.token,
                    channel_id=channel.id,
                    llm_id=self._db_obj.id,
                )
                session.add(db_webhook)
                await session.commit()
                await session.refresh(db_webhook)

        return WebhookProxy(db_webhook=db_webhook, discord_webhook=webhook)

    async def get_webhooks(self) -> List[WebhookProxy]:
        """
        Fetch the list of webhooks associated with the LLM.

        Args:
            bot (commands.Bot): The Discord bot instance.

        Returns:
            List[discord.Webhook]: The list of webhooks associated with the LLM.
        """
        bot = svc.get(Bot)
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
        webhooks = []
        async with Session() as session:
            llm = (
                await session.scalars(
                    select(LLM)
                    .options(selectinload(LLM.webhooks))
                    .where(LLM.id == self._db_obj.id)
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
                            f"Error fetching webhook {db_webhook.id} for LLM {self._db_obj.name}: {e}"
                        )
            else:
                logger.error(f"Error fetching LLM {self._db_obj.name}")

        return webhooks

    async def generate_raw_response(
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
                max_tokens=self._db_obj.max_tokens,
                **{key: val for key, val in sampling_config.items() if val is not None},
                api_base=self._db_obj.api_base,
                api_key=self._db_obj.api_key,
                stop=["\n<"],
            )
            return response
        except Exception as e:
            logger.exception(f"Error in generate_response: {str(e)}")
            raise

    def get_system_prompt(self, guild_name: str, channel_name: str) -> str:
        return f"""\
{self._db_obj.system_prompt}

You are: {self._db_obj.name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {guild_name}
Current Discord Channel: {channel_name}
    """

    async def mentioned_in_message(self, message: MessageProxy) -> bool:
        mentioned = f"@{self.name.lower()}" in message.content.lower()
        if mentioned:
            return True

        webhook = await self.get_webhook(message.channel.id)

    async def delete(self) -> None:
        """
        Delete the LLM from the database.
        """
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
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
            "api_base": self._db_obj.api_base,
            "llm_name": self._db_obj.llm_name,
            "api_key": self._db_obj.api_key,
            "max_tokens": self._db_obj.max_tokens,
            "system_prompt": self._db_obj.system_prompt,
            "context_length": self._db_obj.context_length,
            "message_limit": self._db_obj.message_limit,
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
        if self._db_obj.avatar:
            source_avatar_path = AVATAR_DIR / self._db_obj.avatar
            if os.path.exists(source_avatar_path):
                file_extension = os.path.splitext(self._db_obj.avatar)[1]
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
            Session: type[AsyncSession] = svc.get(type[AsyncSession])
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

        logger.info(
            f"Avatar set for LLM {self._db_obj.name} and its webhooks: {filename}"
        )

    async def respond(self, channel: "ChannelProxy") -> None:
        """
        Generate a response and post it in the given channel.

        Args:
            channel (ChannelProxy): The channel to post the response in.
        """
        history = await channel.history(limit=self._db_obj.message_limit)
        webhook = await self.get_webhook(channel.id)
        guild = await channel.get_guild()

        bot = await svc.aget(Bot)

        messages: List[str] = []
        if self._db_obj.system_prompt is not None:
            messages.append(self._db_obj.system_prompt)
        for message in reversed(history):
            if not message.content:
                continue

            if message.webhook_id:
                try:
                    msg_webhook = await bot.fetch_webhook(message.webhook_id)
                except NotFound as e:
                    continue
                username = msg_webhook.name
            else:
                username = message.author.name
            content = f"<{username}>: {message.content}"
            messages.append(content)

        try:
            # Generate the response
            response = await self.generate_raw_response(
                [LiteLLMMessage(role="system", content="\n".join(messages))]
            )
            response_str = response.choices[0].message.content

            match = regex.match(r"^<(?<username>[^>]*)>: (?<message>.*)$", response_str)

            if not match:
                await webhook.send(response_str)
                logger.warning(
                    f"{self._db_obj.name} didn't include a username before their message"
                )
                return

            username = match.group("username")
            message = match.group("message")

            if username == self._db_obj.name:
                # If the message is from this LLM, send it
                await webhook.send(message)
            else:
                # Otherwise, pass control to other LLM, if it exists
                other_llm = await LLMProxy.get_by_name(username, self._db_obj.guild_id)
                if other_llm:
                    await other_llm.respond(channel)
                elif member := guild.get_member_named(username):
                    # Or, if it's a human's username, mention them
                    await webhook.send(f"<@{member.id}>")

        except Exception as e:
            logger.exception(f"Error in respond method: {str(e)}")
            # Optionally, you could send an error message to the channel here
