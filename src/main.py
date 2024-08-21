import asyncio
import textwrap
from datetime import datetime
from itertools import groupby
from typing import List, Dict, Union, Iterable

import discord
import yaml
from litellm import acompletion, CustomStreamWrapper
from litellm.types.utils import ModelResponse
from pydantic import BaseModel

DISCORD_MESSAGE_MAX_CHARS = 2000

class LiteLLMConfig(BaseModel):
    api_base: str
    model_name: str
    api_key: str
    max_tokens: int
    temperature: float


class ChatConfig(BaseModel):
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
    message_limit: int


class Config(BaseModel):
    bots: List[BotConfig]

class LiteLLMMessage(BaseModel):
    role: str
    content: str


# Load configuration
with open('../config.yml', 'r') as config_file:
    config_dict = yaml.safe_load(config_file)
    config = Config(**config_dict)


class DiscordBot(discord.Client):
    def __init__(self, bot_config: BotConfig):
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = bot_config

    async def on_ready(self):
        print(f'{self.user} has connected to Discord! INVITE URL: https://discord.com/api/oauth2/authorize?client_id={self.config.discord.client_id}&permissions=412317273088&scope=bot')

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        if self.user.mentioned_in(message):
            async with message.channel.typing():
                try:
                    history: List[LiteLLMMessage] = await self.fetch_message_history(message.channel)

                    system_prompt = f"""\
{self.config.system_prompt}

You are: {self.user.name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {message.guild.name}
Current Discord Channel: {message.channel.name}
Your Discord ID: {self.user.id}
"""

                    messages: List[Dict[str, str]] = [
                        {"role": "system", "content": system_prompt},
                        *history,
                    ]

                    await self.stream_llm_response(messages=messages, channel=message.channel)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await message.channel.send(f"[Script error: {e}]")

    async def fetch_message_history(self, channel: Union[discord.TextChannel, discord.DMChannel]) -> List[LiteLLMMessage]:
        discord_history: Iterable[discord.Message] = reversed([
            message
            async for message in channel.history(limit=self.config.message_limit)
        ])

        # group adjacent messages from the same user
        # this saves some tokens on repeated metadata
        history = []
        for _, message_group in groupby(discord_history, lambda a: a.author):
            message_group = list(message_group)
            first_message = message_group[0]
            role: str = "assistant" if first_message.author == self.user else "user"
            msg_content = "\n\n".join((message.content for message in message_group))
            content = f"""\
<content>
{msg_content}
</content>
<metadata>
Author: {first_message.author.name}
Author ID: {first_message.author.id}
Sent at: {first_message.created_at}
</metadata>
"""

            history.append(LiteLLMMessage(role=role, content=content))

        return history

    async def generate_response(self, messages: List[Dict[str, str]]) -> Union[ModelResponse, CustomStreamWrapper]:
        try:
            response = await acompletion(
                model=self.config.litellm.model_name,
                messages=messages,
                max_tokens=self.config.litellm.max_tokens,
                temperature=self.config.litellm.temperature,
                api_base=self.config.litellm.api_base,
                api_key=self.config.litellm.api_key,
                stop=["</content>"]
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {e}")
            raise

    async def stream_llm_response(self, messages: List[Dict[str, str]], channel: discord.TextChannel) -> str:
        response = await self.generate_response(messages)
        response_str = response.choices[0].message.content

        if "<content>" in response_str:
            response_str = response_str.split("<content>", 1)[1]
        if "</content>" in response_str:
            response_str = response_str.split("</content>", 1)[0]

        print(f"{self.config.name}: {response_str}")
        await self.send_message(response_str, channel)

        return response_str

    async def send_message(self, content: str, channel: discord.TextChannel) -> None:
        content = content.strip()

        if not content:
            return None

        messages = self.break_messages(content)

        for message in messages:
            await channel.send(message)

    @staticmethod
    def break_messages(content: str) -> List[str]:
        messages = [
            nonempty_message
            for paragraph in content.split("\n\n")
            for message in textwrap.wrap(paragraph, width=DISCORD_MESSAGE_MAX_CHARS)
            if (nonempty_message := message.strip())
        ]
        return messages


def main():
    bots = [DiscordBot(bot_config) for bot_config in config.bots]
    loop = asyncio.get_event_loop()
    for bot in bots:
        loop.create_task(bot.start(bot.config.discord.bot_token))
    loop.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bots stopped.")
