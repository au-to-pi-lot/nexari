from typing import List, Optional, TYPE_CHECKING

import sqlalchemy
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, Text, UniqueConstraint, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.db.models import Base
from src.db.models.guild import Guild

if TYPE_CHECKING:
    from src.db.models.webhook import Webhook


class LLMCreate(BaseModel):
    """Pydantic model for creating a new LLM.

    Attributes:
        name (str): The name of the LLM.
        guild_id (int): The ID of the guild the LLM belongs to.
        api_base (str): The base URL for the LLM API.
        llm_name (str): The name of the specific LLM model.
        api_key (str): The API key for accessing the LLM.
        max_tokens (int): The maximum number of tokens for LLM responses.
        system_prompt (Optional[str]): The system prompt for the LLM.
        context_length (int): The context length for the LLM.
        message_limit (int): The message limit for the LLM.
        instruct_tuned (bool): Whether the LLM is an instruct model.
        message_formatter (str): The message formatter for the LLM.
        enabled (bool): Whether the LLM will respond to messages.
        temperature (float): The temperature parameter for the LLM.
        top_p (Optional[float]): The top_p parameter for the LLM.
        top_k (Optional[int]): The top_k parameter for the LLM.
        frequency_penalty (Optional[float]): The frequency penalty parameter for the LLM.
        presence_penalty (Optional[float]): The presence penalty parameter for the LLM.
        repetition_penalty (Optional[float]): The repetition penalty parameter for the LLM.
        min_p (Optional[float]): The min_p parameter for the LLM.
        top_a (Optional[float]): The top_a parameter for the LLM.
    """

    name: str
    guild_id: int
    api_base: str
    llm_name: str
    api_key: str
    max_tokens: int
    system_prompt: Optional[str]
    context_length: int
    message_limit: int
    instruct_tuned: bool
    message_formatter: Optional[str]
    enabled: bool
    temperature: float = Field(default=1.0)
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    min_p: Optional[float] = None
    top_a: Optional[float] = None


class LLMUpdate(BaseModel):
    """
    Pydantic model for updating an existing LLM.

    Attributes:
        name (Optional[str]): The new name for the LLM.
        api_base (Optional[str]): The new base URL for the LLM API.
        llm_name (Optional[str]): The new name of the specific LLM model.
        api_key (Optional[str]): The new API key for accessing the LLM.
        max_tokens (Optional[int]): The new maximum number of tokens for LLM responses.
        system_prompt (Optional[str]): The new system prompt for the LLM.
        context_length (Optional[int]): The new context length for the LLM.
        message_limit (Optional[int]): The new message limit for the LLM.
        instruct_tuned (Optional[bool]): The new instruction setting for the LLM.
        message_formatter (Optional[str]): The new message formatter for the LLM.
        enabled (Optional[bool]): Whether the LLM will respond to messages.
        temperature (Optional[float]): The new temperature parameter for the LLM.
        top_p (Optional[float]): The new top_p parameter for the LLM.
        top_k (Optional[int]): The new top_k parameter for the LLM.
        frequency_penalty (Optional[float]): The new frequency penalty parameter for the LLM.
        presence_penalty (Optional[float]): The new presence penalty parameter for the LLM.
        repetition_penalty (Optional[float]): The new repetition penalty parameter for the LLM.
        min_p (Optional[float]): The new min_p parameter for the LLM.
        top_a (Optional[float]): The new top_a parameter for the LLM.
        avatar (Optional[str]): The new avatar for the LLM.
    """

    name: Optional[str] = None
    api_base: Optional[str] = None
    llm_name: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    context_length: Optional[int] = None
    message_limit: Optional[int] = None
    instruct_tuned: Optional[bool] = None
    message_formatter: Optional[str] = None
    enabled: Optional[bool] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    min_p: Optional[float] = None
    top_a: Optional[float] = None
    avatar: Optional[bytes] = None


class LLM(Base):
    """
    SQLAlchemy model representing an LLM configuration.

    Attributes:
        id (int): The unique identifier for the LLM.
        name (str): The name of the LLM.
        guild_id (int): The ID of the guild the LLM belongs to.
        api_base (str): The base URL for the LLM API.
        llm_name (str): The name of the specific LLM model.
        api_key (str): The API key for accessing the LLM.
        max_tokens (int): The maximum number of tokens for LLM responses.
        system_prompt (Optional[str]): The system prompt for the LLM.
        context_length (int): The context length for the LLM.
        message_limit (int): The message limit for the LLM.
        instruct_tuned (bool): The instruction setting for the LLM.
        message_formatter (str): The message formatter for the LLM.
        enabled (bool): Whether the LLM will respond to messages.
        temperature (float): The temperature parameter for the LLM.
        top_p (Optional[float]): The top_p parameter for the LLM.
        top_k (Optional[int]): The top_k parameter for the LLM.
        frequency_penalty (Optional[float]): The frequency penalty parameter for the LLM.
        presence_penalty (Optional[float]): The presence penalty parameter for the LLM.
        repetition_penalty (Optional[float]): The repetition penalty parameter for the LLM.
        min_p (Optional[float]): The min_p parameter for the LLM.
        top_a (Optional[float]): The top_a parameter for the LLM.
        avatar (Optional[str]): The avatar for the LLM.
        guild (Guild): The Guild object this LLM belongs to.
        webhooks (List[Webhook]): List of Webhook objects associated with this LLM.
    """

    __tablename__ = "llm"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guild.id"))
    api_base: Mapped[str] = mapped_column(Text)
    llm_name: Mapped[str] = mapped_column(Text)
    api_key: Mapped[str] = mapped_column(Text)
    max_tokens: Mapped[int]
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    context_length: Mapped[int]
    message_limit: Mapped[int]
    instruct_tuned: Mapped[bool] = mapped_column(server_default=sqlalchemy.sql.true())
    message_formatter: Mapped[str] = mapped_column(server_default="irc")
    enabled: Mapped[bool] = mapped_column(server_default=sqlalchemy.sql.true())

    temperature: Mapped[float] = mapped_column(nullable=False, default=1.0)
    top_p: Mapped[Optional[float]]
    top_k: Mapped[Optional[int]]
    frequency_penalty: Mapped[Optional[float]]
    presence_penalty: Mapped[Optional[float]]
    repetition_penalty: Mapped[Optional[float]]
    min_p: Mapped[Optional[float]]
    top_a: Mapped[Optional[float]]

    avatar: Mapped[Optional[str]]

    guild: Mapped["Guild"] = relationship(back_populates="llms", foreign_keys=guild_id)
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="llm")

    __table_args__ = (UniqueConstraint("name", "guild_id", name="uq_name_guild_id"),)

    @validates("temperature")
    def validate_temperature(self, key: str, temperature: float) -> float:
        """
        Validate the temperature parameter.

        Args:
            key (str): The key being validated.
            temperature (float): The temperature value to validate.

        Returns:
            float: The validated temperature value.

        Raises:
            ValueError: If the temperature is out of the valid range.
        """
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(
                f"`temperature` out of range: {temperature}. Value must be between 0.0 and 2.0 inclusive."
            )
        return temperature

    @validates("top_p")
    def validate_top_p(self, key: str, top_p: Optional[float]) -> Optional[float]:
        """
        Validate the top_p parameter.

        Args:
            key (str): The key being validated.
            top_p (Optional[float]): The top_p value to validate.

        Returns:
            Optional[float]: The validated top_p value.

        Raises:
            ValueError: If the top_p is out of the valid range.
        """
        if top_p is not None and not 0.0 <= top_p <= 1.0:
            raise ValueError(
                f"`top_p` out of range: {top_p}. Value must be between 0.0 and 1.0 inclusive."
            )
        return top_p

    @validates("top_k")
    def validate_top_k(self, key: str, top_k: Optional[int]) -> Optional[int]:
        """
        Validate the top_k parameter.

        Args:
            key (str): The key being validated.
            top_k (Optional[int]): The top_k value to validate.

        Returns:
            Optional[int]: The validated top_k value.

        Raises:
            ValueError: If the top_k is negative.
        """
        if top_k is not None and top_k < 0:
            raise ValueError(f"`top_k` must be non-negative: {top_k}.")
        return top_k

    @validates("frequency_penalty", "presence_penalty")
    def validate_penalty(self, key: str, value: Optional[float]) -> Optional[float]:
        """
        Validate the frequency_penalty and presence_penalty parameters.

        Args:
            key (str): The key being validated.
            value (Optional[float]): The penalty value to validate.

        Returns:
            Optional[float]: The validated penalty value.

        Raises:
            ValueError: If the penalty is out of the valid range.
        """
        if value is not None and not -2.0 <= value <= 2.0:
            raise ValueError(
                f"`{key}` out of range: {value}. Value must be between -2.0 and 2.0 inclusive."
            )
        return value

    @validates("repetition_penalty")
    def validate_repetition_penalty(
        self, key: str, value: Optional[float]
    ) -> Optional[float]:
        """
        Validate the repetition_penalty parameter.

        Args:
            key (str): The key being validated.
            value (Optional[float]): The repetition_penalty value to validate.

        Returns:
            Optional[float]: The validated repetition_penalty value.

        Raises:
            ValueError: If the repetition_penalty is negative.
        """
        if value is not None and value < 0.0:
            raise ValueError(f"`repetition_penalty` must be non-negative: {value}.")
        return value

    @validates("min_p")
    def validate_min_p(self, key: str, min_p: Optional[float]) -> Optional[float]:
        """
        Validate the min_p parameter.

        Args:
            key (str): The key being validated.
            min_p (Optional[float]): The min_p value to validate.

        Returns:
            Optional[float]: The validated min_p value.

        Raises:
            ValueError: If the min_p is out of the valid range.
        """
        if min_p is not None and not 0.0 <= min_p <= 1.0:
            raise ValueError(
                f"`min_p` out of range: {min_p}. Value must be between 0.0 and 1.0 inclusive."
            )
        return min_p

    @validates("top_a")
    def validate_top_a(self, key: str, top_a: Optional[float]) -> Optional[float]:
        """
        Validate the top_a parameter.

        Args:
            key (str): The key being validated.
            top_a (Optional[float]): The top_a value to validate.

        Returns:
            Optional[float]: The validated top_a value.

        Raises:
            ValueError: If the top_a is negative.
        """
        if top_a is not None and top_a < 0.0:
            raise ValueError(f"`top_a` must be non-negative: {top_a}.")
        return top_a
