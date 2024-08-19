from typing import List, Dict, Optional, Union

import discord
import yaml
from discord.ext import commands
from litellm import acompletion, CustomStreamWrapper
from litellm.types.utils import ModelResponse

# Load configuration
with open('config.yml', 'r') as config_file:
    config = yaml.safe_load(config_file)

# Initialize Discord bot
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
bot: commands.Bot = commands.Bot(command_prefix='!', intents=intents)

# Get the bot's client ID from the configuration
client_id: Optional[str] = config['discord']['client_id']
if not client_id:
    raise ValueError("DISCORD_CLIENT_ID is not set in the configuration.")

# LiteLLM configuration
litellm_config = config['litellm']
api_base: str = litellm_config['api_base']
model_name: str = litellm_config['model_name']
api_key: str = litellm_config['api_key']
max_tokens: int = litellm_config['max_tokens']
temperature: float = litellm_config['temperature']

# Chat configuration
thinking_message: str = config['chat']['thinking_message']
context_length: int = config['chat']['context_length']

system_prompt: str = config['system_prompt']


@bot.event
async def on_ready() -> None:
    print(f'{bot.user} has connected to Discord!')


async def fetch_message_history(channel: Union[discord.TextChannel, discord.DMChannel], context_length: int) -> List[
    Dict[str, str]]:
    history: List[Dict[str, str]] = []
    async for msg in channel.history(limit=context_length):
        role: str = "assistant" if msg.author == bot.user else "user"
        history.append({
            'role': role,
            'content': msg.content
        })
    return list(reversed(history))


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                history: List[Dict[str, str]] = await fetch_message_history(message.channel, context_length)

                messages: List[Dict[str, str]] = [
                    {"role": "system", "content": system_prompt},
                    *history,
                ]

                await stream_llm_response(messages=messages, trigger_message=message)
            except Exception as e:
                print(f"An error occurred: {e}")
                await message.channel.send("I apologize, but I encountered an error while processing your request.")

    await bot.process_commands(message)


async def stream_llm_response(messages: List[Dict[str, str]], trigger_message: discord.Message) -> str:
    response: str = ""
    sent_message: discord.Message = await trigger_message.reply(thinking_message)
    buffer: str = ""
    in_code_block: bool = False

    async for chunk in await generate_response(messages):
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
    if message.content == thinking_message and message.edited_at is None:
        return await message.edit(content=content.strip())

    elif len(message.content) + len(content) > 1900:
        if in_code_block:
            # finish code block in current message
            await message.edit(content=message.content + "\n```")
            # continue code block in next message
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


async def generate_response(messages: List[Dict[str, str]]) -> Union[ModelResponse, CustomStreamWrapper]:
    try:
        response = await acompletion(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            api_base=api_base,
            api_key=api_key,
            stream=True
        )
        return response
    except Exception as e:
        print(f"Error in generate_response: {e}")
        raise


# Get the bot token from the configuration
bot_token = config['discord']['bot_token']
if not bot_token:
    raise ValueError("DISCORD_BOT_TOKEN is not set in the configuration.")

try:
    bot.run(bot_token)
except KeyboardInterrupt:
    print("Bot stopped.")
