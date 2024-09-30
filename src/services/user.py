from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models.user import User, UserCreate, UserUpdate

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def create_user(self, user_data: UserCreate) -> User:
        user = User(**user_data.dict())
        self.session.add(user)
        await self.session.commit()
        return user

    async def update_user(self, user: User, update_data: UserUpdate) -> User:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(user, key, value)
        await self.session.commit()
        return user

    async def delete_user(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.commit()

    async def get_all_users(self) -> List[User]:
        result = await self.session.execute(select(User))
        return result.scalars().all()

    async def get_or_create_user(self, user_id: int, user_data: UserCreate) -> User:
        user = await self.get_user(user_id)
        if not user:
            user = await self.create_user(user_data)
        return user
