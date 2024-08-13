# LLM-backed Discord Chatbot

This project implements a Discord chatbot using discord.py and llama.cpp. The bot responds to mentions and direct messages using a local LLM (Language Model) powered by llama.cpp.

## Prerequisites

- Python 3.8 or higher
- A Discord bot token
- A llama.cpp compatible model file

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/llm-discord-bot.git
   cd llm-discord-bot
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Download a llama.cpp compatible model file and place it in a known location.

## Configuration

1. Open `main.py` and replace `'YOUR_BOT_TOKEN'` with your actual Discord bot token.

2. In the same file, update the `model_path` in the Llama initialization:
   ```python
   llm = Llama(model_path="path/to/your/llama/model.bin")
   ```
   Replace `"path/to/your/llama/model.bin"` with the actual path to your model file.

## Running the Bot

To start the bot, run:

```
python main.py
```

The bot will connect to Discord and print a message when ready.

## Usage

- Mention the bot or send it a direct message to get a response.
- The bot will use the LLM to generate responses based on the input.

## Note

Ensure that your Discord bot has the necessary permissions in your server, including the ability to read messages and send responses.
