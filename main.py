import discord
from discord.ext import commands
from llama_cpp import Llama

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Llama model
llm = Llama(model_path="path/to/your/llama/model.bin")

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
            response = llm(prompt, max_tokens=100, stop=["Human:", "AI:"], echo=False)
            ai_response = response['choices'][0]['text'].strip()
        
        await message.reply(ai_response)

    await bot.process_commands(message)

# Replace 'YOUR_BOT_TOKEN' with your actual Discord bot token
bot.run('YOUR_BOT_TOKEN')
