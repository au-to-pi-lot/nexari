import inspect
import os
import asyncio
import signal
from typing import List, Dict, Optional, Union, Any, AsyncGenerator
import discord
from discord.ext import commands
from llama_cpp import Llama
import yaml
import requests
from llama_cpp.llama_chat_format import ChatFormatter, get_chat_completion_handler
from tqdm import tqdm

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
model_url: Optional[str] = config['llm']['model_url']
model_path: str = config['llm']['model_path']

if not os.path.exists(model_path) and model_url:
    print(f"Downloading model from {model_url}")
    download_model(model_url, model_path)
elif not os.path.exists(model_path):
    raise ValueError("Model file not found and no URL provided for download.")

# Get settings from configuration
max_tokens: int = config['llm']['max_tokens']
temperature: float = config['llm']['temperature']
context_length: int = config['llm']['context_length']
stop_tokens: Optional[List[str]] = config['llm']['stop_tokens']
gpu_layers: int = config['llm']['gpu_layers']
enable_flash_attention: bool = config['llm']['enable_flash_attention']
n_threads: int = config['llm']['n_threads']
n_threads_batch: int = config['llm']['n_threads_batch']

# Initialize Llama model
try:
    llm: Llama = Llama(
        model_path=model_path,
        n_ctx=context_length,
        n_gpu_layers=gpu_layers,
        use_mlock=False,
        use_mmap=True,
        flash_attn=enable_flash_attention,
        type_k=2,  # 4-bit KV
        type_v=2,
        n_threads=n_threads,
        n_threads_batch=n_threads_batch,
    )
    print(f"Llama model initialized successfully with 4-bit KV buffers and 4-bit cache, using {n_threads} threads and {n_threads_batch} batch threads")
except Exception as e:
    print(f"Error initializing Llama model: {e}")
    raise

# Get thinking message from configuration
thinking_message: str = config['chat']['thinking_message']

system_prompt: str = config['system_prompt']


@bot.event
async def on_ready() -> None:
    print(f'{bot.user} has connected to Discord!')


async def fetch_message_history(channel: Union[discord.TextChannel, discord.DMChannel], context_length: int) -> List[
    Dict[str, str]]:
    history: List[Dict[str, str]] = []
    total_tokens: int = 0
    async for msg in channel.history(limit=None):
        role: str = format_role(msg.author)
        name: str = format_name(msg.author)
        msg_content: str = msg.content
        msg_tokens: List[int] = llm.tokenize(msg_content.encode())
        msg_token_count: int = len(msg_tokens)
        if total_tokens + msg_token_count > context_length // 2:
            break
        history.append({
            'role': role,
            'name': name,
            'content': msg_content
        })
        total_tokens += msg_token_count
    return list(reversed(history))


def format_prompt(messages: List[Dict[str, str]], begin_next_message: bool = True) -> str:
    message_template = "<|start_header_id|>{role}<|end_header_id|>\n\n{name}{content}"
    stop_token = "<|eot_id|>"

    prompt = "".join((
        message_template.format(**message) + stop_token
        for message in messages
    ))

    if begin_next_message:
        prompt += message_template.format(role=format_role(bot.user), name=format_name(bot.user), content="")

    return prompt


def format_role(user: discord.User) -> str:
    return "assistant" if user == bot.user else "user"

def format_name(user: discord.User) -> str:
    return f"{user.name} (<@{user.id}>): "

@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return


    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                history: List[Dict[str, str]] = await fetch_message_history(message.channel, context_length)

                # Prepare the messages for the chat completion
                messages: List[Dict[str, str]] = [
                    {"role": "system", "name": "", "content": system_prompt},
                    *history
                ]

                ai_response: str = await stream_tokens(messages, message)
            except Exception as e:
                print(f"An error occurred: {e}")
                await message.channel.send("I apologize, but I encountered an error while processing your request.")

    await bot.process_commands(message)


async def stream_tokens(messages: List[Dict[str, str]], message: discord.Message) -> str:
    response: str = ""
    sent_message: discord.Message = await message.reply(thinking_message)
    buffer: str = ""
    in_code_block: bool = False

    prompt: str = format_prompt(messages)

    print(prompt)
    
    async for token in async_create_completion(prompt):
        new_text: str = token['choices'][0]['text']
        if new_text:
            response += new_text
            buffer += new_text

            if '```' in new_text:
                sent_message = await update_message(sent_message, buffer, in_code_block=in_code_block)
                buffer = ""
                in_code_block = not in_code_block

            if len(buffer) >= 20:
                sent_message = await update_message(sent_message, buffer, in_code_block=in_code_block)
                buffer = ""

    if buffer:
        await update_message(sent_message, buffer)

    return response


async def async_create_completion(prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
    completion = llm.create_completion(
        prompt,
        max_tokens=max_tokens,
        stop=stop_tokens,
        temperature=temperature,
        top_k=0,
        top_p=0,
        min_p=0.05,
        repeat_penalty=1.5,

        stream=True
    )
    for token in completion:
        yield token
        await asyncio.sleep(0.01)  # Small delay to allow other tasks to run


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



def signal_handler(sig, frame):
    print("Ctrl+C pressed. Shutting down gracefully...")
    asyncio.create_task(bot.close())


signal.signal(signal.SIGINT, signal_handler)

# Get the bot token from the environment variable
try:
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
except KeyboardInterrupt:
    print("Bot stopped.")
