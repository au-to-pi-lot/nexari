from abc import ABC
from typing import Any, Optional, Self

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import LLM
from src.services import svc
from src.types.proxy import BaseProxy


class LLMProxy(BaseProxy[None, LLM]):
    def __init__(self, llm: LLM) -> None:
        super().__init__(None, llm)

    @classmethod
    async def get(cls, identifier: int) -> Optional[Self]:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            llm = await session.get(LLM, identifier)
            if llm is None:
                return None
            return LLMProxy(llm)


    async def save(self) -> None:
        pass