import os
import discord
from discord.ext import commands
from llama_cpp import Llama
from dotenv import load_dotenv
from jinja2 import Template

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

# Load Jinja2 template
with open('prompt_template.j2', 'r') as file:
    template = Template(file.read())

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            # Fetch the message history
            history = []
            async for msg in message.channel.history(limit=10):
                history.append({
                    'role': f"{msg.author.display_name} ({msg.author.id})",
                    'content': msg.content
                })
            history.reverse()  # Reverse to get chronological order

            # Add the current message to history
            history.append({
                'role': f"{message.author.display_name} ({message.author.id})",
                'content': message.content
            })

            # Render the prompt using the Jinja2 template
            prompt = template.render(messages=history, bot=bot)
            
            response = llm(prompt, max_tokens=max_tokens, stop=["### Instruction:", "### Response:"], echo=False, temperature=temperature)
            ai_response = response['choices'][0]['text'].strip()
        
        # Remove any remaining "### Response:" from the beginning of the response
        ai_response = ai_response.lstrip("### Response:").strip()
        await message.reply(ai_response)

    await bot.process_commands(message)

# Get the bot token from the environment variable
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
