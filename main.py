import asyncio
from typing import List, Dict, Union

import discord
import yaml
from discord.ext import commands
from litellm import acompletion, CustomStreamWrapper
from litellm.types.utils import ModelResponse
from pydantic import BaseModel


class LiteLLMConfig(BaseModel):
    api_base: str
    model_name: str
    api_key: str
    max_tokens: int
    temperature: float


class ChatConfig(BaseModel):
    thinking_message: str
    context_length: int


class DiscordConfig(BaseModel):
    bot_token: str
    client_id: str


class BotConfig(BaseModel):
    name: str
    discord: DiscordConfig
    litellm: LiteLLMConfig
    chat: ChatConfig
    system_prompt: str


class Config(BaseModel):
    bots: List[BotConfig]


# Load configuration
with open('config.yml', 'r') as config_file:
    config_dict = yaml.safe_load(config_file)
    config = Config(**config_dict)


async def fetch_message_history(channel: Union[discord.TextChannel, discord.DMChannel], context_length: int) -> List[
    Dict[str, str]]:
    history: List[Dict[str, str]] = []
    async for msg in channel.history(limit=context_length):
        role: str = "assistant" if msg.author.bot else "user"
        history.append({
            'role': role,
            'content': msg.content
        })
    return list(reversed(history))


class DiscordBot:
    def __init__(self, bot_config: BotConfig):
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        self.bot: commands.Bot = commands.Bot(command_prefix="!", intents=intents)
        self.config = bot_config

        @self.bot.event
        async def on_ready() -> None:
            print(f'{self.bot.user} has connected to Discord! INVITE URL: https://discord.com/api/oauth2/authorize?client_id={self.config.client_id}&permissions=412317273088&scope=bot')

        @self.bot.event
        async def on_message(message: discord.Message) -> None:
            await self.handle_message(message)

    async def handle_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return

        if self.bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
            async with message.channel.typing():
                try:
                    history: List[Dict[str, str]] = await fetch_message_history(message.channel,
                                                                                self.config.chat.context_length)

                    messages: List[Dict[str, str]] = [
                        {"role": "system", "content": self.config.system_prompt},
                        *history,
                    ]

                    await self.stream_llm_response(messages=messages, trigger_message=message)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await message.channel.send("I apologize, but I encountered an error while processing your request.")

        await self.bot.process_commands(message)

    async def generate_response(self, messages: List[Dict[str, str]]) -> Union[ModelResponse, CustomStreamWrapper]:
        try:
            response = await acompletion(
                model=self.config.litellm.model_name,
                messages=messages,
                max_tokens=self.config.litellm.max_tokens,
                temperature=self.config.litellm.temperature,
                api_base=self.config.litellm.api_base,
                api_key=self.config.litellm.api_key,
                stream=True
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {e}")
            raise

    async def stream_llm_response(self, messages: List[Dict[str, str]], trigger_message: discord.Message) -> str:
        response: str = ""
        sent_message: discord.Message = await trigger_message.reply(self.config.chat.thinking_message)
        buffer: str = ""
        in_code_block: bool = False

        async for chunk in await self.generate_response(messages):
            if chunk:
                response += chunk
                buffer += chunk

                if '```' in chunk:
                    sent_message = await self.update_message(sent_message, buffer, in_code_block=in_code_block)
                    buffer = ""
                    in_code_block = not in_code_block

                if len(buffer) >= 20:
                    sent_message = await self.update_message(sent_message, buffer, in_code_block=in_code_block)
                    buffer = ""

        if buffer:
            await self.update_message(sent_message, buffer)

        return response

    async def update_message(self, message: discord.Message, content: str, in_code_block: bool = False) -> discord.Message:
        if message.content == self.config.chat.thinking_message and message.edited_at is None:
            return await message.edit(content=content.strip())

        elif len(message.content) + len(content) > 1900:
            if in_code_block:
                await message.edit(content=message.content + "\n```")
                return await message.channel.send("```\n" + content.strip())

            return await message.channel.send(content.strip())

        elif "\n\n" in content and not in_code_block:
            paragraphs = content.split("\n\n")
            message = await message.edit(content=message.content + paragraphs[0])
            for paragraph in paragraphs[1:]:
                if len(paragraph.strip()) == 0:
                    continue
                message = await message.channel.send(paragraph)
            return message

        else:
            return await message.edit(content=message.content + content)

    async def start(self):
        return await self.bot.start(self.config.discord.bot_token)


def main():
    bots = [DiscordBot(bot_config) for bot_config in config.bots]
    loop = asyncio.get_event_loop()
    for bot in bots:
        loop.create_task(bot.start())
    loop.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bots stopped.")
