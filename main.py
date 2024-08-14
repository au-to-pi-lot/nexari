import os
import asyncio
import discord
from discord.ext import commands
from llama_cpp import Llama
from dotenv import load_dotenv
import requests
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Get the bot's client ID from the environment variable
client_id = os.getenv('DISCORD_CLIENT_ID')
if not client_id:
    raise ValueError("DISCORD_CLIENT_ID is not set in the environment variables.")

# Function to download model
def download_model(url, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    mode = 'ab' if os.path.exists(save_path) else 'wb'
    
    with open(save_path, mode) as file, tqdm(
        desc=save_path,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(chunk_size=1024):
            size = file.write(data)
            progress_bar.update(size)

# Get model path or download if not available
model_url = os.getenv('LLAMA_MODEL_URL')
model_path = os.getenv('LLAMA_MODEL_PATH', 'models/model.bin')

if not os.path.exists(model_path) and model_url:
    print(f"Downloading model from {model_url}")
    download_model(model_url, model_path)
elif not os.path.exists(model_path):
    raise ValueError("Model file not found and no URL provided for download.")

# Get settings from environment variables
max_tokens = int(os.getenv('MAX_TOKENS', 100))
temperature = float(os.getenv('TEMPERATURE', 0.7))
context_length = int(os.getenv('CONTEXT_LENGTH', 1000))
stop_tokens = os.getenv('STOP_TOKENS', '').split(',') if os.getenv('STOP_TOKENS') else None
gpu_layers = int(os.getenv('GPU_LAYERS', 0))
enable_flash_attention = os.getenv('ENABLE_FLASH_ATTENTION', 'false').lower() == 'true'
enable_tensorcores = os.getenv('ENABLE_TENSORCORES', 'false').lower() == 'true'
chat_template = os.getenv('CHAT_TEMPLATE', 'llama-2')

# Initialize Llama model
try:
    llm = Llama(
        model_path=model_path,
        n_ctx=context_length,
        n_gpu_layers=gpu_layers,
        use_mlock=False,
        use_mmap=True,
        use_flash_attention=enable_flash_attention,
        use_tensor_split=enable_tensorcores,
        chat_format=chat_template
    )
    print("Llama model initialized successfully")
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
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

async def fetch_message_history(channel, context_length):
    history = []
    total_tokens = 0
    async for msg in channel.history(limit=None):
        role = "user" if msg.author != bot.user else "assistant"
        msg_content = f"{msg.author.display_name} ({msg.author.id}): {msg.content}"
        msg_tokens = llm.tokenize(msg_content.encode())
        msg_token_count = len(msg_tokens)
        if total_tokens + msg_token_count > context_length:
            break
        history.append({
            'role': role,
            'content': msg_content
        })
        total_tokens += msg_token_count
    return list(reversed(history))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                history = await fetch_message_history(message.channel, context_length)
                
                # Add the current message to history
                current_msg_content = f"{message.author.display_name} ({message.author.id}): {message.content}"
                history.append({
                    'role': 'user',
                    'content': current_msg_content
                })

                # Prepare the messages for the chat completion
                messages = [
                    {"role": "system", "content": system_prompt},
                    *history
                ]
                
                ai_response = await stream_tokens(messages, message)
            
                # The response is already properly formatted, no need to remove "### Response:"
            except Exception as e:
                print(f"An error occurred: {e}")
                await message.channel.send("I apologize, but I encountered an error while processing your request.")

    await bot.process_commands(message)

async def stream_tokens(messages, message):
    response = ""
    sent_message = await message.reply("Thinking...")
    buffer = ""
    in_code_block = False

    async for token in llm.create_chat_completion(messages, max_tokens=max_tokens, stop=stop_tokens, temperature=temperature, stream=True):
        new_text = token['choices'][0]['delta'].get('content', '')
        if new_text:
            response += new_text
            buffer += new_text

            if '```' in new_text:
                in_code_block = not in_code_block

            if not in_code_block and ('\n\n' in buffer or len(buffer) >= 1900):
                await update_message(sent_message, buffer)
                buffer = ""

    if buffer:
        await update_message(sent_message, buffer)

    return response

async def update_message(message, content):
    if len(message.content) + len(content) > 1900:
        message = await message.channel.send(content.strip())
    else:
        await message.edit(content=message.content + content)
    await asyncio.sleep(0.5)  # Add a small delay to avoid rate limiting

# Get the bot token from the environment variable
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
