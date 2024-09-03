import logging
from datetime import datetime
from typing import List, Optional, Self

import discord
from discord.ext.commands import Bot
from litellm import acompletion
from litellm.types.utils import ModelResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.const import AVATAR_DIR
from src.db.models import LLM, Webhook
from src.db.models.llm import LLMCreate
from src.proxies import ChannelProxy, WebhookProxy
from src.services import svc
from src.types.litellm_message import LiteLLMMessage
from src.types.proxy import BaseProxy

logger = logging.getLogger(__name__)


class LLMProxy(BaseProxy[None, LLM]):
    def __init__(self, llm: LLM) -> None:
        super().__init__(None, llm)

    @classmethod
    async def get(cls, identifier: int) -> Optional[Self]:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
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
        async with svc.get(type[AsyncSession])() as session:
            stmt = select(LLM).where(LLM.guild_id == guild_id)
            result = await session.execute(stmt)
            llms = result.scalars().all()
            return [cls(llm) for llm in llms]

    @classmethod
    async def get_by_name(cls, name: str, guild_id: int) -> Optional[Self]:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
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
    async def create(cls, llm_data: LLMCreate) -> Self:
        async with svc.get(type[AsyncSession])() as session:
            db_llm = LLM(**llm_data.dict())
            session.add(db_llm)
            await session.commit()
        return cls(db_llm)

    async def save(self) -> None:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
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
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        bot = svc.get(Bot)

        channel = await ChannelProxy.get(channel_id)

        async with Session() as session:
            query = select(Webhook).where(
                Webhook.channel_id == channel_id and Webhook.llm_id == self._db_obj
            )
            db_webhook = (await session.scalars(query)).one_or_none()

            if db_webhook:
                webhook = await bot.fetch_webhook(webhook_id=db_webhook.id)
            else:
                avatar = None
                if self.llm.avatar:
                    avatar_path = AVATAR_DIR / self.llm.avatar
                    if avatar_path.exists():
                        with open(avatar_path, "rb") as avatar_file:
                            avatar = avatar_file.read()

                webhook = await channel.create_webhook(
                    name=self.llm.name, avatar=avatar
                )
                db_webhook = Webhook(
                    id=webhook.id,
                    token=webhook.token,
                    channel_id=channel.id,
                    llm_id=self.llm.id,
                )
                session.add(db_webhook)
                await session.commit()

        return WebhookProxy(db_webhook=db_webhook, discord_webhook=webhook)

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
                stop=["<|begin_metadata|>"],
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

    def mentioned_in_message(self, message: discord.Message) -> bool:
        mentioned = f"@{self.llm.name.lower()}" in message.content.lower()
        if mentioned:
            return True

        webhook = self.get_webhook(message.channel)

    async def delete(self) -> None:
        """
        Delete the LLM from the database.
        """
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            await session.delete(self._db_obj)
            await session.commit()
