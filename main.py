import os
import asyncio
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
llm = Llama(model_path=os.getenv('LLAMA_MODEL_PATH'), verbose=False)

# Get settings from environment variables
max_tokens = int(os.getenv('MAX_TOKENS', 100))
temperature = float(os.getenv('TEMPERATURE', 0.7))
context_length = int(os.getenv('CONTEXT_LENGTH', 1000))
stop_tokens = ["### Instruction:", "### Response:"]

# Define Jinja2 templates as strings
message_template = "{{ role }}: {{ content }}"

prompt_template = """
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
You are {{ bot.user.display_name }}, a helpful AI assistant in a Discord chat. Respond to the following conversation:

{% for message in messages %}
{{ message_template | format(role=message.role, content=message.content) }}
{% endfor %}

### Response:
"""

# Create Jinja2 Template objects
message_template = Template(message_template)
prompt_template = Template(prompt_template)

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
            total_tokens = 0
            async for msg in message.channel.history(limit=None):
                msg_role = f"{msg.author.display_name} ({msg.author.id})"
                msg_content = message_template.render(role=msg_role, content=msg.content)
                msg_tokens = llm.tokenize(msg_content.encode())
                msg_token_count = len(msg_tokens)
                if total_tokens + msg_token_count > context_length:
                    break
                history.append({
                    'role': msg_role,
                    'content': msg.content
                })
                total_tokens += msg_token_count
            history.reverse()  # Reverse to get chronological order

            # Add the current message to history
            current_msg_role = f"{message.author.display_name} ({message.author.id})"
            current_msg_content = message_template.render(role=current_msg_role, content=message.content)
            current_msg_tokens = llm.tokenize(current_msg_content.encode())
            current_msg_token_count = len(current_msg_tokens)
            history.append({
                'role': current_msg_role,
                'content': message.content
            })

            # Render the prompt using the Jinja2 template
            prompt = prompt_template.render(messages=history, bot=bot)
            
            ai_response = await stream_tokens(prompt, message)
        
        # Remove any remaining "### Response:" from the beginning of the response
        ai_response = ai_response.lstrip("### Response:").strip()

    await bot.process_commands(message)

async def stream_tokens(prompt, message):
    response = ""
    sent_message = await message.reply("Thinking...")
    current_paragraph = ""
    async for token in llm(prompt, max_tokens=max_tokens, stop=stop_tokens, echo=False, temperature=temperature, stream=True):
        new_text = token['choices'][0]['text']
        response += new_text
        current_paragraph += new_text

        if '\n\n' in current_paragraph:
            # New paragraph detected
            paragraphs = current_paragraph.split('\n\n')
            for i, paragraph in enumerate(paragraphs[:-1]):
                if i == 0:
                    await sent_message.edit(content=paragraph.strip())
                else:
                    sent_message = await message.channel.send(paragraph.strip())
            current_paragraph = paragraphs[-1]

        if len(current_paragraph) % 20 == 0:  # Edit message every 20 characters
            await sent_message.edit(content=current_paragraph)
            await asyncio.sleep(0.5)  # Add a small delay to avoid rate limiting

    # Send any remaining content
    if current_paragraph.strip():
        await sent_message.edit(content=current_paragraph.strip())

    return response

# Get the bot token from the environment variable
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
