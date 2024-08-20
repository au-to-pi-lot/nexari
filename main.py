import asyncio
from datetime import datetime
from typing import List, Dict, Union, Optional

import discord
import yaml
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
                    history: List[Dict[str, str]] = await self.fetch_message_history(message.channel,
                                                                                self.config.chat.context_length)

                    system_prompt = f"""\
{self.config.system_prompt}

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
                    await message.channel.send("I apologize, but I encountered an error while processing your request.")

    async def fetch_message_history(self, channel: Union[discord.TextChannel, discord.DMChannel],
                                    context_length: int) -> List[
        Dict[str, str]]:
        history: List[Dict[str, str]] = []
        async for msg in channel.history(limit=context_length):
            role: str = "assistant" if msg.author == self.user else "user"
            history.append({
                'role': role,
                'content': f"""\
<content>
{msg.content}
</content>
<metadata>
Author: {msg.author.name}
Author ID: {msg.author.id}
Sent at: {msg.created_at}
</metadata>
"""

            })
        return list(reversed(history))

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

        print(f"{self.config.name}: {response_str}")
        await self.send_message(response_str, channel)

        return response_str

    async def send_message(self, content: str, channel: discord.TextChannel) -> None:
        content = content.strip()

        if not content:
            return None

        messages = [
            nonempty_message
            for paragraph in content.split("\n\n")
            for message in textwrap.wrap(paragraph, width=DISCORD_MESSAGE_MAX_CHARS)
            if (nonempty_message := message.strip())
        ]

        for message in messages:
            await channel.send(message)

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
