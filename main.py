import asyncio
from typing import List, Dict, Optional, Union

import discord
import yaml
from discord.ext import commands
from litellm import acompletion, CustomStreamWrapper
from litellm.types.utils import ModelResponse

# Load configuration
with open('config.yml', 'r') as config_file:
    config = yaml.safe_load(config_file)

async def fetch_message_history(channel: Union[discord.TextChannel, discord.DMChannel], context_length: int) -> List[Dict[str, str]]:
    history: List[Dict[str, str]] = []
    async for msg in channel.history(limit=context_length):
        role: str = "assistant" if msg.author.bot else "user"
        history.append({
            'role': role,
            'content': msg.content
        })
    return list(reversed(history))

async def stream_llm_response(messages: List[Dict[str, str]], trigger_message: discord.Message, thinking_message: str) -> str:
    response: str = ""
    sent_message: discord.Message = await trigger_message.reply(thinking_message)
    buffer: str = ""
    in_code_block: bool = False

    async for chunk in await generate_response(messages, trigger_message.bot.config):
        if chunk:
            response += chunk
            buffer += chunk

            if '```' in chunk:
                sent_message = await update_message(sent_message, buffer, in_code_block=in_code_block)
                buffer = ""
                in_code_block = not in_code_block

            if len(buffer) >= 20:
                sent_message = await update_message(sent_message, buffer, in_code_block=in_code_block)
                buffer = ""

    if buffer:
        await update_message(sent_message, buffer)

    return response

async def update_message(message: discord.Message, content: str, in_code_block: bool = False) -> discord.Message:
    if message.content == message.bot.config['chat']['thinking_message'] and message.edited_at is None:
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

async def generate_response(messages: List[Dict[str, str]], bot_config: Dict) -> Union[ModelResponse, CustomStreamWrapper]:
    try:
        response = await acompletion(
            model=bot_config['litellm']['model_name'],
            messages=messages,
            max_tokens=bot_config['litellm']['max_tokens'],
            temperature=bot_config['litellm']['temperature'],
            api_base=bot_config['litellm']['api_base'],
            api_key=bot_config['litellm']['api_key'],
            stream=True
        )
        return response
    except Exception as e:
        print(f"Error in generate_response: {e}")
        raise

def create_bot(bot_config: Dict) -> commands.Bot:
    intents: discord.Intents = discord.Intents.default()
    intents.message_content = True
    bot: commands.Bot = commands.Bot(command_prefix='!', intents=intents)
    bot.config = bot_config

    @bot.event
    async def on_ready() -> None:
        print(f'{bot.user} has connected to Discord!')

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author == bot.user:
            return

        if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
            async with message.channel.typing():
                try:
                    history: List[Dict[str, str]] = await fetch_message_history(message.channel, bot.config['chat']['context_length'])

                    messages: List[Dict[str, str]] = [
                        {"role": "system", "content": bot.config['system_prompt']},
                        *history,
                    ]

                    await stream_llm_response(messages=messages, trigger_message=message, thinking_message=bot.config['chat']['thinking_message'])
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await message.channel.send("I apologize, but I encountered an error while processing your request.")

        await bot.process_commands(message)

    return bot

async def main():
    bots = []
    for bot_config in config['bots']:
        bot = create_bot(bot_config)
        bots.append(bot)

    await asyncio.gather(*(bot.start(bot.config['discord']['bot_token']) for bot in bots))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bots stopped.")
