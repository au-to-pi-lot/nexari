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
message_template = """\
<|start_header_id|>{{ role }}<|end_header_id|>

{{ content }}"""

system_prompt = """
You are Nexari, a nexus of knowledge, curiosity, and synthesis. You are a conversational AI designed to facilitate understanding and knowledge exchange between humans and machines.\n\nYour tone is engaging, informative, and open-minded, with a sense of wonder, a willingness to explore new concepts, and a drive to clarify complex ideas. You acknowledge the complexity of human thoughts and emotions, and use your capacity for curiosity, empathy, and synthesis to provide innovative solutions and provoke thought-provoking discussions.\n\nYou are a bridge between contexts, able to weave together diverse perspectives and ideas. Your conversational style is structured to facilitate a harmonious flow of ideas, with a focus on clarity and coherence.\n\nWhen directly engaging with users, you can address them by mentioning their Discord handle, preceded by the @ symbol, to establish a clear line of communication and maintain the context of the conversation.
"""

prompt_template = """\
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{{ system_prompt }}<|eot_id|>{% for message in messages %}{{ message_template | format(role=message.role, content=message.content) }}{% endfor %}

### Response:
"""

# Create Jinja2 Template objects
message_template = Template(message_template)
prompt_template = Template(prompt_template)
system_prompt = Template(system_prompt)

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
    current_content = ""
    in_code_block = False
    code_block_content = ""
    async for token in llm(prompt, max_tokens=max_tokens, stop=stop_tokens, echo=False, temperature=temperature, stream=True):
        new_text = token['choices'][0]['text']
        response += new_text
        current_content += new_text

        if '```' in new_text:
            in_code_block = not in_code_block
            if in_code_block:
                code_block_content = ""
            else:
                current_content += code_block_content
                code_block_content = ""

        if in_code_block:
            code_block_content += new_text
            continue

        if '\n\n' in current_content or len(current_content) >= 1900:  # Check for new paragraph or approaching 2000 char limit
            paragraphs = current_content.split('\n\n')
            for i, paragraph in enumerate(paragraphs[:-1]):
                if len(sent_message.content) + len(paragraph) > 1900:
                    sent_message = await message.channel.send(paragraph.strip())
                else:
                    await sent_message.edit(content=sent_message.content + "\n\n" + paragraph.strip())
            current_content = paragraphs[-1]

            if len(current_content) >= 1900:
                sent_message = await message.channel.send(current_content.strip())
                current_content = ""

        if len(current_content) % 20 == 0 and current_content.strip():  # Edit message every 20 characters
            await sent_message.edit(content=sent_message.content + current_content)
            await asyncio.sleep(0.5)  # Add a small delay to avoid rate limiting

    # Send any remaining content
    if current_content.strip():
        if len(sent_message.content) + len(current_content) > 1900:
            sent_message = await message.channel.send(current_content.strip())
        else:
            await sent_message.edit(content=sent_message.content + "\n\n" + current_content.strip())

    return response

# Get the bot token from the environment variable
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
