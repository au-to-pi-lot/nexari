# LLM-backed Discord Chatbot

This project implements a Discord chatbot using discord.py and llama.cpp. The bot responds to mentions and direct messages using a local LLM (Language Model) powered by llama.cpp.

## Prerequisites

- Conda (Miniconda or Anaconda)
- A Discord bot token
- A llama.cpp compatible model file
- NVIDIA GPU with CUDA support (for GPU acceleration)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/llm-discord-bot.git
   cd llm-discord-bot
   ```

2. Make the setup script executable:
   ```
   chmod +x setup.sh
   ```

3. Run the setup script:
   ```
   ./setup.sh
   ```

   This script will create a Conda environment, install all required dependencies including the CUDA Toolkit, and compile llama-cpp-python with CUBLAS support for GPU acceleration.

4. Download a llama.cpp compatible model file and place it in a known location.

Note: The setup script will install the CUDA Toolkit using Conda. Make sure you have an NVIDIA GPU with CUDA support for GPU acceleration.

## Configuration

1. Copy the `config-example.yml` file to a new file named `config.yml`:
   ```
   cp config-example.yml config.yml
   ```

2. Open the `config.yml` file and update the values:
   - Replace `your_discord_bot_token_here` with your actual Discord bot token.
   - Replace `your_discord_client_id_here` with your actual Discord client ID.
   - Update `models/model.bin` with the actual path to your model file.
   - Adjust other settings as needed (see comments in the file for explanations).

3. The `config-example.yml` file contains explanations for all available settings. Refer to it for more information on configuring your bot.

Note: The `config.yml` file is gitignored to prevent accidental commits of sensitive information.

## Running the Bot

1. Make the start script executable:
   ```
   chmod +x start.sh
   ```

2. To start the bot, run:
   ```
   ./start.sh
   ```

The bot will connect to Discord and print a message when ready.

## Usage

- Mention the bot or send it a direct message to get a response.
- The bot will use the LLM to generate responses based on the input.

## Note

Ensure that your Discord bot has the necessary permissions in your server, including the ability to read messages and send responses.
