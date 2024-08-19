import asyncio
from datetime import datetime
from typing import List, Dict, Union

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


async def fetch_message_history(channel: Union[discord.TextChannel, discord.DMChannel], context_length: int) -> List[
    Dict[str, str]]:
    history: List[Dict[str, str]] = []
    async for msg in channel.history(limit=context_length):
        role: str = "assistant" if msg.author.bot else "user"
        history.append({
            'role': role,
            'content': f"<metadata>{msg.author.name} (Author ID: {msg.author.id}, Created At: {msg.created_at.isoformat()})</metadata>\n\n<content>{msg.content}</content>"

        })
    return list(reversed(history))


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

        print(f'{message.author.name} sent message: {message.content}')

        if self.user.mentioned_in(message):
            async with message.channel.typing():
                try:
                    history: List[Dict[str, str]] = await fetch_message_history(message.channel,
                                                                                self.config.chat.context_length)

                    system_prompt = f"""\
{self.config.system_prompt}

Current Time: {datetime.now().isoformat()}
Current Discord Guild: {message.guild.name}
Current Discord Channel: {message.channel.name}
Your Discord ID: {self.user.id}
"""

                    print(system_prompt)

                    messages: List[Dict[str, str]] = [
                        {"role": "system", "content": self.config.system_prompt},
                        *history,
                    ]

                    await self.stream_llm_response(messages=messages, channel=message.channel)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await message.channel.send("I apologize, but I encountered an error while processing your request.")

    async def generate_response(self, messages: List[Dict[str, str]]) -> Union[ModelResponse, CustomStreamWrapper]:
        try:
            response = await acompletion(
                model=self.config.litellm.model_name,
                messages=messages,
                max_tokens=self.config.litellm.max_tokens,
                temperature=self.config.litellm.temperature,
                api_base=self.config.litellm.api_base,
                api_key=self.config.litellm.api_key,
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {e}")
            raise

    async def stream_llm_response(self, messages: List[Dict[str, str]], channel: discord.TextChannel) -> str:
        response: str = ""
        sent_message: Optional[discord.Message] = None
        buffer: str = ""
        in_code_block: bool = False

        response = await self.generate_response(messages)

        if isinstance(response, CustomStreamWrapper):
            async for chunk in response:
                if chunk:
                    response += chunk
                    buffer += chunk

                    if '```' in chunk:
                        sent_message = await self.update_message(sent_message, buffer, channel, in_code_block=in_code_block)
                        buffer = ""
                        in_code_block = not in_code_block

                    if len(buffer) >= 20:
                        sent_message = await self.update_message(sent_message, buffer, channel, in_code_block=in_code_block)
                        buffer = ""

            if buffer:
                await self.update_message(sent_message, buffer, channel)
        else:
            print(f"{self.config.name}: {response.choices[0].message.content}")
            await self.update_message(sent_message, response.choices[0].message.content, channel)

        return response

    async def update_message(self, message: Optional[discord.Message], content: str, channel: discord.TextChannel, in_code_block: bool = False) -> discord.Message:
        if message is None:
            return await channel.send(content.strip())
        else:
            return await self.edit_message(message=message, new_content=message.content + content, in_code_block=in_code_block)

    async def edit_message(self, message: discord.Message, new_content: str, in_code_block: bool = False):
        if "\n\n" in new_content and not in_code_block:
            paragraphs = new_content.split("\n\n")
            message = await self.edit_message(message=message, new_content=paragraphs[0])
            for paragraph in paragraphs[1:]:
                if len(paragraph.strip()) == 0:
                    continue
                message = await message.channel.send(paragraph)
            return message

        if len(new_content) > 1900:
            if in_code_block:
                await message.edit(content=message.content + "\n```")
                # assumes that message after code block is less than the discord message length limit
                return await message.channel.send("```\n" + new_content.strip())

            return await message.channel.send(new_content.strip())

        else:
            return await message.edit(content=new_content)

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
