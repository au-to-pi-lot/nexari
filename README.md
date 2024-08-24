# LLM-backed Discord Chatbot

This project implements a Discord chatbot using discord.py and LiteLLM. The bot responds to mentions and direct messages using a Language Model (LLM) powered by LiteLLM.

## Prerequisites

- Python 3.12 or higher
- A Discord bot token
- An API key for your chosen LLM provider (e.g., OpenAI)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/llm-discord-bot.git
   cd llm-discord-bot
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Copy the `config-example.yml` file to a new file named `config.yml`:
   ```
   cp config-example.yml config.yml
   ```

2. Open the `config.yml` file and update the values:
   - Replace `your_discord_bot_token_here` with your actual Discord bot token.
   - Replace `your_discord_client_id_here` with your actual Discord client ID.
   - Update the `llms` section with your chosen LLM provider's details.
   - Adjust other settings as needed (see comments in the file for explanations).

3. The `config-example.yml` file contains explanations for all available settings. Refer to it for more information on configuring your bot.

Note: The `config.yml` file is gitignored to prevent accidental commits of sensitive information.

## Running the Bot

To start the bot, run:
```
python src/main.py
```

The bot will connect to Discord and print a message when ready.

## Usage

- Mention the bot or send it a direct message to get a response.
- The bot will use the configured LLM to generate responses based on the input.

## Development

- To run tests: `pytest tests/`
- To apply database migrations: `alembic upgrade head`
- To create a new migration: `alembic revision -m "Description of changes"`

## Note

Ensure that your Discord bot has the necessary permissions in your server, including the ability to read messages and send responses.
