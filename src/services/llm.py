from typing import Optional, List, Any
import logging
import os
import shutil

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import aiohttp
from litellm import acompletion
from litellm.types.utils import ModelResponse

from src import message_formatters
from src.db.models.llm import LLM, LLMCreate, LLMUpdate
from src.db.models.webhook import Webhook
from src.db.models.guild import Guild
from src.const import AVATAR_DIR
from src.services.discord_client import bot
from src.services.guild import GuildService
from src.services.webhook import WebhookService
from src.types.litellm_message import LiteLLMMessage

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, llm_id: int) -> Optional[LLM]:
        return await self.session.get(LLM, llm_id)

    async def get_by_name(self, name: str, guild_id: int) -> Optional[LLM]:
        stmt = select(LLM).where(LLM.name == name, LLM.guild_id == guild_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_guild(self, guild_id: int) -> List[LLM]:
        stmt = select(LLM).where(LLM.guild_id == guild_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, llm_data: LLMCreate) -> LLM:
        llm = LLM(**llm_data.model_dump())
        self.session.add(llm)
        await self.session.commit()
        return llm

    async def update(self, llm: LLM, update_data: LLMUpdate) -> LLM:
        old_name = llm.name
        for key, value in update_data.items():
            if key == "name" and value != old_name:
                # If the name has changed, update all associated webhooks
                webhooks = await self.get_webhooks(llm)
                for webhook in webhooks:
                    discord_webhook = await bot.fetch_webhook(webhook.id)
                    try:
                        await discord_webhook.edit(name=value)
                    except Exception as e:
                        logger.error(f"Failed to update webhook {webhook.id} name: {e}")
                        raise
            elif key == "message_formatter":
                if value not in message_formatters.formatters:
                    raise ValueError(f"Invalid message formatter: {value}")

            setattr(llm, key, value)
        await self.session.commit()
        return llm

    async def delete(self, llm: LLM) -> None:
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
                discord_webhook = await bot.fetch_webhook(webhook.id)
                await discord_webhook.edit(avatar=avatar)
            except Exception as e:
                logger.error(f"Failed to update avatar for webhook {webhook.id}: {e}")

        logger.info(f"Avatar set for LLM {llm.name} and its webhooks: {filename}")

    async def get_or_create_webhook(self, llm: LLM, channel: discord.TextChannel) -> Webhook:
        webhook_service = WebhookService(session=self.session)
        db_webhook = await webhook_service.get_by_llm_channel(channel.id, llm.id)
        if db_webhook is None:
            avatar_data = None
            if llm.avatar is not None:
                avatar_path = AVATAR_DIR / llm.avatar
                if avatar_path.exists():
                    with open(avatar_path, "rb") as avatar_file:
                        avatar_data = avatar_file.read()

            discord_webhook = await channel.create_webhook(
                name=llm.name,
                avatar=avatar_data,
            )
            db_webhook = await webhook_service.create(discord_webhook, llm)

        return db_webhook


    async def get_webhooks(self, llm: LLM) -> List[Webhook]:
        stmt = select(LLM).options(selectinload(LLM.webhooks)).where(LLM.id == llm.id)
        result = await self.session.execute(stmt)
        llm_with_webhooks = result.scalar_one_or_none()
        return llm_with_webhooks.webhooks if llm_with_webhooks else []

    async def generate_instruct_response(self, llm: LLM, messages: List[LiteLLMMessage]) -> ModelResponse:
        try:
            sampling_config = {
                "temperature": llm.temperature,
                "top_p": llm.top_p,
                "top_k": llm.top_k,
                "frequency_penalty": llm.frequency_penalty,
                "presence_penalty": llm.presence_penalty,
                "repetition_penalty": llm.repetition_penalty,
                "min_p": llm.min_p,
                "top_a": llm.top_a,
            }
            response = await acompletion(
                model=llm.llm_name,
                messages=messages,
                max_tokens=llm.max_tokens,
                **{key: val for key, val in sampling_config.items() if val is not None},
                api_base=llm.api_base,
                api_key=llm.api_key,
                stop=[],
            )
            return response
        except Exception as e:
            logger.exception(f"Error in generate_instruct_response: {str(e)}")
            raise

    async def generate_simulator_response(self, llm: LLM, prompt: str, stop_words: list[str] = None) -> dict[str, Any]:
        if stop_words is None:
            stop_words = []

        url = f"{llm.api_base}/completions"
        headers = {
            "Authorization": f"Bearer {llm.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Nexari/0.1.0"
        }
        data = {
            "model": llm.llm_name,
            "prompt": prompt,
            "max_tokens": llm.max_tokens,
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

    async def copy_llm(self, llm: LLM, new_name: str) -> LLM:
        new_llm_data = {
            "name": new_name,
            "guild_id": llm.guild_id,
            "api_base": llm.api_base,
            "llm_name": llm.llm_name,
            "api_key": llm.api_key,
            "max_tokens": llm.max_tokens,
            "system_prompt": llm.system_prompt,
            "context_length": llm.context_length,
            "message_limit": llm.message_limit,
            "instruct_tuned": llm.instruct_tuned,
            "enabled": llm.enabled,
            "message_formatter": llm.message_formatter,
            "temperature": llm.temperature,
            "top_p": llm.top_p,
            "top_k": llm.top_k,
            "frequency_penalty": llm.frequency_penalty,
            "presence_penalty": llm.presence_penalty,
            "repetition_penalty": llm.repetition_penalty,
            "min_p": llm.min_p,
            "top_a": llm.top_a,
        }

        # Copy the avatar file if it exists
        if llm.avatar:
            source_avatar_path = AVATAR_DIR / llm.avatar
            if os.path.exists(source_avatar_path):
                file_extension = os.path.splitext(llm.avatar)[1]
                new_avatar_filename = f"{new_name}{file_extension}"
                new_avatar_path = AVATAR_DIR / new_avatar_filename
                shutil.copy2(source_avatar_path, new_avatar_path)
                new_llm_data["avatar"] = new_avatar_filename
            else:
                logger.warning(
                    f"Avatar file {source_avatar_path} not found. New LLM will not have an avatar."
                )

        new_llm = await self.create(LLMCreate(**new_llm_data))
        return new_llm

    async def get_simulator(self, guild_id: int) -> Optional[LLM]:
        """
        Get the simulator LLM for a given guild.

        Args:
            guild_id (int): The ID of the guild.

        Returns:
            Optional[LLM]: The simulator LLM if found, None otherwise.
        """
        guild_service = GuildService(session=self.session)
        guild = await guild_service.get(guild_id)

        if guild and guild.simulator_id:
            return await self.get(guild.simulator_id)
        return None

    async def respond(self, llm: LLM, channel: discord.TextChannel, history: List[discord.Message]) -> None:
        """
        Generate a response and post it in the given channel.

        Args:
            llm (LLM): The LLM to use for generating the response.
            channel (discord.TextChannel): The channel to post the response in.
            history (List[discord.Message]): The message history to use for context.
        """
        webhook = await self.get_or_create_webhook(llm, channel)
        guild_service = GuildService(session=self.session)
        guild = await guild_service.get(channel.guild.id)

        try:
            message_formatter = message_formatters.get_message_formatter(llm.message_formatter)
            if not message_formatter:
                raise ValueError(f"Invalid message formatter: {llm.message_formatter}")

            if llm.instruct_tuned:
                messages = await message_formatter.format_instruct(history, llm.system_prompt, webhook)
                response = await self.generate_instruct_response(llm, messages)
                response_str = response.choices[0].message.content
            else:
                llms_in_guild = await self.get_by_guild(guild.id)
                prompt = await message_formatter.format_simulator(history, llm.system_prompt, webhook, channel, [llm.name for llm in llms_in_guild], llm.name)
                response = await self.generate_simulator_response(llm, prompt, ['\n\n\n'])
                response_str = response["choices"][0]["text"]

            logger.info(f"{llm.name} (#{channel.name}): {response_str}")

            if response_str == "":
                logger.info(f"{llm.name} declined to respond in channel {channel.id}")
                return

            parse_response = await message_formatter.parse_messages(response_str)
            response_messages = parse_response.split_messages
            response_username = parse_response.username

            if response_username is None:
                # If no usernames were found, assume it's from this LLM
                response_username = llm.name

            if response_username == llm.name:
                # If the message is from this LLM, send it
                discord_webhook = await bot.fetch_webhook(webhook.id)
                for message in response_messages:
                    await discord_webhook.send(message)
                logger.info(f"Msg in channel {channel.id} from {response_username}: {parse_response.complete_message}")
            else:
                # Otherwise, pass control to other LLM, if it exists
                other_llm = await self.get_by_name(response_username, guild.id)
                if other_llm:
                    logger.info(f"{llm.name} passed to {other_llm.name}")
                    await self.respond(other_llm, channel, history)
                elif member := channel.guild.get_member_named(response_username):
                    # Or, if it's a human's username, mention them
                    discord_webhook = await bot.fetch_webhook(webhook.id)
                    await discord_webhook.send(f"<@{member.id}>")
                else:
                    # If no matching LLM or user found, send the message as is
                    discord_webhook = await bot.fetch_webhook(webhook.id)
                    for message in response_messages:
                        await discord_webhook.send(message)
                    logger.warning(f"{llm.name} sent a message with unknown username: {response_username}")

        except Exception as e:
            logger.exception(f"Error in respond method: {str(e)}")
