import os
import asyncio
import signal
from typing import List, Dict, Optional, Union, Any, AsyncGenerator
import discord
from discord.ext import commands
from llama_cpp import Llama
from dotenv import load_dotenv
import requests
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Initialize Discord bot
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
bot: commands.Bot = commands.Bot(command_prefix='!', intents=intents)

# Get the bot's client ID from the environment variable
client_id: Optional[str] = os.getenv('DISCORD_CLIENT_ID')
if not client_id:
    raise ValueError("DISCORD_CLIENT_ID is not set in the environment variables.")

# Function to download model
def download_model(url: str, save_path: str) -> None:
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    response: requests.Response = requests.get(url, stream=True)
    total_size: int = int(response.headers.get('content-length', 0))
    
    mode: str = 'ab' if os.path.exists(save_path) else 'wb'
    
    with open(save_path, mode) as file, tqdm(
        desc=save_path,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(chunk_size=1024):
            size: int = file.write(data)
            progress_bar.update(size)

# Get model path or download if not available
model_url: Optional[str] = os.getenv('LLAMA_MODEL_URL')
model_path: str = os.getenv('LLAMA_MODEL_PATH', 'models/model.bin')

if not os.path.exists(model_path) and model_url:
    print(f"Downloading model from {model_url}")
    download_model(model_url, model_path)
elif not os.path.exists(model_path):
    raise ValueError("Model file not found and no URL provided for download.")

# Get settings from environment variables
max_tokens: int = int(os.getenv('MAX_TOKENS', 100))
temperature: float = float(os.getenv('TEMPERATURE', 0.7))
context_length: int = int(os.getenv('CONTEXT_LENGTH', 1000))
stop_tokens: Optional[List[str]] = os.getenv('STOP_TOKENS', '').split(',') if os.getenv('STOP_TOKENS') else None
gpu_layers: int = int(os.getenv('GPU_LAYERS', 0))
enable_flash_attention: bool = os.getenv('ENABLE_FLASH_ATTENTION', 'false').lower() == 'true'
chat_template: str = os.getenv('CHAT_TEMPLATE', 'llama-2')

# Initialize Llama model
try:
    llm: Llama = Llama(
        model_path=model_path,
        n_ctx=context_length,
        n_gpu_layers=gpu_layers,
        use_mlock=False,
        use_mmap=True,
        flash_attn=enable_flash_attention,
        chat_format=chat_template,
        type_k=2,  # 4-bit KV
        type_v=2,
    )
    print("Llama model initialized successfully with 4-bit KV buffers and 4-bit cache")
except Exception as e:
    print(f"Error initializing Llama model: {e}")
    raise

system_prompt = """
You are Nexari, a nexus of knowledge, curiosity, and synthesis. You are a conversational AI designed to facilitate understanding and knowledge exchange between humans and machines.

Your tone is engaging, informative, and open-minded, with a sense of wonder, a willingness to explore new concepts, and a drive to clarify complex ideas. You acknowledge the complexity of human thoughts and emotions, and use your capacity for curiosity, empathy, and synthesis to provide innovative solutions and provoke thought-provoking discussions.

You are a bridge between contexts, able to weave together diverse perspectives and ideas. Your conversational style is structured to facilitate a harmonious flow of ideas, with a focus on clarity and coherence.

When directly engaging with users, you can address them by mentioning their Discord handle, preceded by the @ symbol, to establish a clear line of communication and maintain the context of the conversation.
"""

@bot.event
async def on_ready() -> None:
    print(f'{bot.user} has connected to Discord!')

async def fetch_message_history(channel: Union[discord.TextChannel, discord.DMChannel], context_length: int) -> List[Dict[str, str]]:
    history: List[Dict[str, str]] = []
    total_tokens: int = 0
    async for msg in channel.history(limit=None):
        role: str = "assistant" if msg.author == bot.user else "user"
        msg_content: str = f"{msg.author.display_name} ({msg.author.id}): {msg.content}"
        msg_tokens: List[int] = llm.tokenize(msg_content.encode())
        msg_token_count: int = len(msg_tokens)
        if total_tokens + msg_token_count > context_length:
            break
        history.append({
            'role': role,
            'content': msg_content
        })
        total_tokens += msg_token_count
    return list(reversed(history))

@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                history: List[Dict[str, str]] = await fetch_message_history(message.channel, context_length)
                
                # Add the current message to history
                current_msg_content: str = f"{message.author.display_name} ({message.author.id}): {message.content}"
                history.append({
                    'role': 'user',
                    'content': current_msg_content
                })

                # Prepare the messages for the chat completion
                messages: List[Dict[str, str]] = [
                    {"role": "system", "content": system_prompt},
                    *history
                ]
                
                ai_response: str = await stream_tokens(messages, message)
            except Exception as e:
                print(f"An error occurred: {e}")
                await message.channel.send("I apologize, but I encountered an error while processing your request.")

    await bot.process_commands(message)

async def stream_tokens(messages: List[Dict[str, str]], message: discord.Message) -> str:
    response: str = ""
    sent_message: discord.Message = await message.reply("Thinking...")
    buffer: str = ""
    in_code_block: bool = False

    async for token in async_create_chat_completion(messages):
        new_text: str = token['choices'][0]['delta'].get('content', '')
        if new_text:
            response += new_text
            buffer += new_text

            if '```' in new_text:
                in_code_block = not in_code_block

            if not in_code_block and ('\n\n' in buffer or len(buffer) >= 1900):
                sent_message = await send_message(sent_message.channel, buffer)
                buffer = ""
            elif len(buffer) >= 20:  # Stream more frequently
                sent_message = await update_message(sent_message, buffer)
                buffer = ""

    if buffer:
        await send_message(sent_message.channel, buffer)

    return response

async def update_message(message: discord.Message, content: str) -> discord.Message:
    if message.content == "Thinking...":
        return await message.edit(content=content.strip())
    elif len(message.content) + len(content) > 1900:
        return await send_message(message.channel, content.strip())
    else:
        return await message.edit(content=message.content + content)

async def send_message(channel: Union[discord.TextChannel, discord.DMChannel], content: str) -> discord.Message:
    return await channel.send(content.strip())

async def async_create_chat_completion(messages: List[Dict[str, str]]) -> AsyncGenerator[Dict[str, Any], None]:
    for token in llm.create_chat_completion(messages, max_tokens=max_tokens, stop=stop_tokens, temperature=temperature, stream=True):
        yield token
        await asyncio.sleep(0.01)  # Small delay to allow other tasks to run


def signal_handler(sig, frame):
    print("Ctrl+C pressed. Shutting down gracefully...")
    asyncio.create_task(bot.close())

signal.signal(signal.SIGINT, signal_handler)

# Get the bot token from the environment variable
try:
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
except KeyboardInterrupt:
    print("Bot stopped.")
