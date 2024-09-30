from typing import Optional, List
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.db.models.llm import LLM
from src.db.models.webhook import Webhook
from src.const import AVATAR_DIR

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_llm(self, llm_id: int) -> Optional[LLM]:
        return await self.session.get(LLM, llm_id)

    async def get_llm_by_name(self, name: str, guild_id: int) -> Optional[LLM]:
        stmt = select(LLM).where(LLM.name == name, LLM.guild_id == guild_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_llms(self, guild_id: int) -> List[LLM]:
        stmt = select(LLM).where(LLM.guild_id == guild_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_llm(self, **llm_data) -> LLM:
        llm = LLM(**llm_data)
        self.session.add(llm)
        await self.session.commit()
        return llm

    async def update_llm(self, llm: LLM, **update_data) -> LLM:
        for key, value in update_data.items():
            setattr(llm, key, value)
        await self.session.commit()
        return llm

    async def delete_llm(self, llm: LLM) -> None:
        await self.session.delete(llm)
        await self.session.commit()

    async def set_avatar(self, llm: LLM, avatar: bytes, filename: str) -> None:
        avatar_path = AVATAR_DIR / filename

        # Save the avatar file
        with open(avatar_path, "wb") as f:
            f.write(avatar)

        # Update the LLM's avatar in the database
        llm.avatar = filename
        await self.session.commit()

        # Update the avatar for all associated webhooks
        stmt = select(Webhook).where(Webhook.llm_id == llm.id)
        result = await self.session.execute(stmt)
        webhooks = result.scalars().all()

        for webhook in webhooks:
            try:
                # Assuming you have a Discord client instance available
                discord_webhook = await discord_client.fetch_webhook(webhook.id)
                await discord_webhook.edit(avatar=avatar)
            except Exception as e:
                logger.error(f"Failed to update avatar for webhook {webhook.id}: {e}")

        logger.info(f"Avatar set for LLM {llm.name} and its webhooks: {filename}")

    async def get_webhooks(self, llm: LLM) -> List[Webhook]:
        stmt = select(LLM).options(selectinload(LLM.webhooks)).where(LLM.id == llm.id)
        result = await self.session.execute(stmt)
        llm_with_webhooks = result.scalar_one_or_none()
        return llm_with_webhooks.webhooks if llm_with_webhooks else []
