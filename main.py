import os
import asyncio
import signal
from typing import List, Dict, Optional, Union, Any
import discord
from discord.ext import commands
import yaml
from litellm import completion

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

async def fetch_message_history(channel: Union[discord.TextChannel, discord.DMChannel], context_length: int) -> List[Dict[str, str]]:
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
                    {"role": "user", "content": message.content}
                ]

                ai_response: str = await generate_response(messages)
                await message.reply(ai_response)
            except Exception as e:
                print(f"An error occurred: {e}")
                await message.channel.send("I apologize, but I encountered an error while processing your request.")

    await bot.process_commands(message)

async def generate_response(messages: List[Dict[str, str]]) -> str:
    try:
        response = completion(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            api_base=api_base,
            api_key=api_key
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in generate_response: {e}")
        raise

def signal_handler(sig, frame):
    print("Ctrl+C pressed. Shutting down gracefully...")
    asyncio.create_task(bot.close())

signal.signal(signal.SIGINT, signal_handler)

# Get the bot token from the configuration
bot_token = config['discord']['bot_token']
if not bot_token:
    raise ValueError("DISCORD_BOT_TOKEN is not set in the configuration.")

try:
    bot.run(bot_token)
except KeyboardInterrupt:
    print("Bot stopped.")
