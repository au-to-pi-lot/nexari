import os
import discord
from discord.ext import commands
from llama_cpp import Llama
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Llama model
llm = Llama(model_path=os.getenv('LLAMA_MODEL_PATH'))

# Get other settings from environment variables
max_tokens = int(os.getenv('MAX_TOKENS', 100))
stop_sequences = os.getenv('STOP_SEQUENCES', 'Human:,AI:').split(',')
temperature = float(os.getenv('TEMPERATURE', 0.7))

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            prompt = f"Human: {message.content}\nAI:"
            response = llm(prompt, max_tokens=max_tokens, stop=stop_sequences, echo=False, temperature=temperature)
            ai_response = response['choices'][0]['text'].strip()
        
        await message.reply(ai_response)

    await bot.process_commands(message)

# Get the bot token from the environment variable
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
