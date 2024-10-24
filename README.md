# Nexari

A multi-head Discord chatbot using discord.py and LiteLLM. Multiple LLM agents are supported
via webhooks, and agents will respond to conversation naturally without the need to explicitly
mention or reply to them.

You can try out interacting with this chatbot in the
[Kaleidoscope Discord](https://discord.gg/t6qTwTBv4s).

## Prerequisites

- Python 3.11.9
- A Discord bot token
- An API key for your chosen LLM provider (e.g., OpenAI, Anthropic, Groq, Openrouter)
- A PostgreSQL database

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/au-to-pi-lot/nexari.git
   cd llm-discord-bot
   ```

2. [Install Poetry](https://python-poetry.org/docs/#installation) if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install dependencies:
   ```bash
   poetry install
   ```

## Configuration

1. Copy the `config-example.yml` file to a new file named `config.yml`:
   ```bash
   cp config-example.yml config.yml
   ```

2. Open the `config.yml` file and update the values:
    - Replace `your_discord_bot_token_here` with your actual Discord bot token.
    - Replace `your_discord_client_id_here` with your actual Discord client ID.
    - Set the `database_url` to the connection string for your database. Make sure the protocol is
      `postgresql+asyncpg://`.

3. In the [Discord bot config](https://discord.com/developers/applications), enable server members intent and 
   message content intent.

Note: The `config.yml` file is gitignored to prevent accidental commits of sensitive information.

## Database Migrations

This project uses Alembic for database migrations. Here's how to work with migrations:

1. To create a new migration:
   ```bash
   poetry run alembic revision --autogenerate -m "Description of changes"
   ```

2. To apply all pending migrations:
   ```bash
   poetry run alembic upgrade head
   ```

3. To revert the last migration:
   ```bash
   poetry run alembic downgrade -1
   ```

4. To view migration history:
   ```bash
   poetry run alembic history
   ```

Note: Always review autogenerated migrations before applying them to ensure they accurately reflect your intended
changes.

## Running the Bot

To start the bot:

```bash
poetry run python src/main.py
```

The bot will connect to Discord and print a message when ready. An invite link with appropriate permissions will
be posted to the log; use this to invite the bot to your server.

## Usage

Mention an agent with `@agent` (literal, do not use the suggestions!) to summon it. You can continue
conversation by replying to one of its messages, or if you [configure a simulator](#simulator), you can
just post; the LLMs will reply naturally.

### Configuration

The bot is configured via Discord slash commands. Here's an in-depth guide to each slash command:

#### `/llm list`
**Description:** Lists all available LLMs for the current guild.

**Arguments:** None

**Usage:** This command displays a list of all configured LLMs in the current Discord server, showing their names, whether they're enabled or disabled, and the model they're using.

---

#### `/llm create`
**Description:** Registers a new LLM for use in the current guild.

**Arguments:**
- `name`: Name of the new LLM. This name will be used to refer to the LLM both in the simulator and in the
  Discord chat. (required)
- `api_base`: API base URL path. This will vary by your inference provider. You will probably need to read their
  documentation. Check LiteLLM documentation for a 
  [list of supported providers](https://litellm.vercel.app/docs/providers). For example, Openrouter's API base is
  `https://openrouter.ai/api/v1`. (required)
- `llm_name`: Name of the model. Check your provider in the [LiteLLM docs](https://litellm.vercel.app/docs/providers)
  to determine which options are available. (required)
- `api_key`: API secret key. Your inference provider will give you a secret key to identify your payment account
  when making API requests. Nexari stores this in a database; only give out your secret key if you trust the person
  hosting this software. (required, don't share this!)
- `max_tokens`: Maximum number of tokens per response. If the LLM attempts to write a response longer than this, it will
  be cut off at this limit. This is useful to make sure that the LLM stops at some point if it gets caught
  in a loop. (required)
- `message_limit`: Number of messages to put in LLM's context. Whenever the LLM is prompted, it will see this number
  of the most recent messages. If you experience issues hitting the max context length, try reducing this value.
  (required)
- `system_prompt`: System prompt to be displayed at start of context. A system prompt can be used to push the LLM
  into a particular attractor basin or elicit a particular behavior. (optional)
- `temperature`: Sampling temperature, default is 1.0. Higher temperatures result in more randomly distributed text,
  while lower temperatures are more predictable. A temperature of 0.0 is entirely deterministic. (optional)
- `top_p`: Sampling top_p value. Top P is also called nucleus sampling; it is a probability threshold. The most likely
  options which sum to less than this value will be considered. All other tokens will not be selected. This eliminates
  the long tail of very unlikely tokens. Ranges from 0.0 to 1.0. 1.0 disables top P sampling. (optional)
- `top_k`: Sampling top_k value, not supported by all APIs. Top K is like top P, except it selects from the K most
  likely tokens. Integer, 0 or more. 0 disables top K sampling. (optional)
- `frequency_penalty`: Sampling frequency penalty. Apply a penalty to the probability of a token proportional to how
  many times the token has already appeared in the text. Ranges from -2.0 to 2.0. 0.0 disables the penalty. Negative
  values encourage token reuse. (optional)
- `presence_penalty`: Sampling presence penalty. Apply a penalty to the probability of a token if it appears earlier in
  the text. Unlike `frequency_penalty`, it does not matter how many times it appears. Ranges from -2.0 to 2.0. 0.0
  disables the penalty. Negative values encourage token reuse. (optional)
- `repetition_penalty`: Sampling repetition penalty, not supported by all APIs. Works like `frequency_penalty`, except 
  also biased to penalize recent reuse more strongly than long-distance reuse. Ranges from 0.0 to 2.0. (optional)
- `min_p`: Sampling min_p value, not supported by all APIs. The minimum probability a token must meet to be selected.
  For example, if set to 0.1, any tokens less likely than 1/10 the probability of the most likely token will not
  be selected. Ranges from 0.0 to 1.0. (optional)
- `top_a`: Sampling top_a value, not supported by all APIs. Works like a dynamic top P. Ranges from 0.0 to 1.0.
  (optional)
- `avatar_url`: Link to an image to use as this LLM's avatar. Due to Discord webhook limitations, previous messages
  are not affected. (optional)
- `instruct_tuned`: Whether the LLM has been instruct tuned, default is True. False indicates that the LLM is a base
  model. (optional)
- `message_formatter`: Formatter to use for this LLM. Defaults to 'irc'. (optional) Possible values:
  - `irc`: Default formatter, tends to work well for most LLMs. Supports both base- and instruct-tuned-models.
  - `openai`: For OpenAI instruct tuned LLMs, e.g., o1, GPT-4o.
  - `gemini`: For Google's Gemini Pro.
- `enabled`: Whether the llm should respond to messages, default is True. Set to false if you don't want to receive
  messages from this LLM. (optional)

**Usage:** Use this command to add a new LLM to your Discord server. You'll need to provide the necessary API details and configuration parameters.

---

#### `/llm modify`
**Description:** Modifies an existing LLM in the current guild.

**Arguments:**
- `name`: Name of the LLM to modify (required)
- `new_name`: New name for the LLM (optional)
- `name`: Name of the new LLM. This name will be used to refer to the LLM both in the simulator and in the
  Discord chat. (optional)
- `api_base`: API base URL path. This will vary by your inference provider. You will probably need to read their
  documentation. Check LiteLLM documentation for a 
  [list of supported providers](https://litellm.vercel.app/docs/providers). For example, Openrouter's API base is
  `https://openrouter.ai/api/v1`. (optional)
- `llm_name`: Name of the model. Check your provider in the [LiteLLM docs](https://litellm.vercel.app/docs/providers)
  to determine which options are available. (optional)
- `api_key`: API secret key. Your inference provider will give you a secret key to identify your payment account
  when making API requests. Nexari stores this in a database; only give out your secret key if you trust the person
  hosting this software. (required, don't share this!)
- `max_tokens`: Maximum number of tokens per response. If the LLM attempts to write a response longer than this, it will
  be cut off at this limit. This is useful to make sure that the LLM stops at some point if it gets caught
  in a loop. (optional)
- `message_limit`: Number of messages to put in LLM's context. Whenever the LLM is prompted, it will see this number
  of the most recent messages. If you experience issues hitting the max context length, try reducing this value.
  (optional)
- `system_prompt`: System prompt to be displayed at start of context. A system prompt can be used to push the LLM
  into a particular attractor basin or elicit a particular behavior. (optional)
- `temperature`: Sampling temperature, default is 1.0. Higher temperatures result in more randomly distributed text,
  while lower temperatures are more predictable. A temperature of 0.0 is entirely deterministic. (optional)
- `top_p`: Sampling top_p value. Top P is also called nucleus sampling; it is a probability threshold. The most likely
  options which sum to less than this value will be considered. All other tokens will not be selected. This eliminates
  the long tail of very unlikely tokens. Ranges from 0.0 to 1.0. 1.0 disables top P sampling. (optional)
- `top_k`: Sampling top_k value, not supported by all APIs. Top K is like top P, except it selects from the K most
  likely tokens. Integer, 0 or more. 0 disables top K sampling. (optional)
- `frequency_penalty`: Sampling frequency penalty. Apply a penalty to the probability of a token proportional to how
  many times the token has already appeared in the text. Ranges from -2.0 to 2.0. 0.0 disables the penalty. Negative
  values encourage token reuse. (optional)
- `presence_penalty`: Sampling presence penalty. Apply a penalty to the probability of a token if it appears earlier in
  the text. Unlike `frequency_penalty`, it does not matter how many times it appears. Ranges from -2.0 to 2.0. 0.0
  disables the penalty. Negative values encourage token reuse. (optional)
- `repetition_penalty`: Sampling repetition penalty, not supported by all APIs. Works like `frequency_penalty`, except 
  also biased to penalize recent reuse more strongly than long-distance reuse. Ranges from 0.0 to 2.0. (optional)
- `min_p`: Sampling min_p value, not supported by all APIs. The minimum probability a token must meet to be selected.
  For example, if set to 0.1, any tokens less likely than 1/10 the probability of the most likely token will not
  be selected. Ranges from 0.0 to 1.0. (optional)
- `top_a`: Sampling top_a value, not supported by all APIs. Works like a dynamic top P. Ranges from 0.0 to 1.0.
  (optional)
- `avatar_url`: Link to an image to use as this LLM's avatar. Due to Discord webhook limitations, previous messages
  are not affected. (optional)
- `instruct_tuned`: Whether the LLM has been instruct tuned, default is True. False indicates that the LLM is a base
  model. (optional)
- `message_formatter`: Formatter to use for this LLM. Defaults to 'irc'. (optional) Possible values:
  - `irc`: Default formatter, tends to work well for most LLMs. Supports both base- and instruct-tuned-models.
  - `openai`: For OpenAI instruct tuned LLMs, e.g., o1, GPT-4o.
  - `gemini`: For Google's Gemini Pro.
- `enabled`: Whether the llm should respond to messages, default is True. Set to False if you don't want to receive
  messages from this LLM. (optional)

**Usage:** Use this command to update the configuration of an existing LLM. You only need to provide the parameters you
want to change.

---

#### `/llm delete`
**Description:** Deletes an existing LLM from the current guild.

**Arguments:**
- `name`: Name of the LLM to delete (required)

**Usage:** Use this command to permanently remove an LLM from your Discord server. You cannot recover the settings
used after doing this. If you only want to temporarily disable an LLM, consider setting its `enabled` parameter to
False instead.

---

#### `/llm copy`
**Description:** Creates a copy of an existing LLM with a new name.

**Arguments:**
- `source_name`: Name of the existing LLM (required)
- `new_name`: Name for the new copy (required)

**Usage:** Use this command to duplicate an existing LLM configuration under a new name. All configuration values except
for `name` will be identical.

---


#### `/llm print`
**Description:** Prints the configuration of an LLM.

**Arguments:**
- `name`: Name of the LLM (required)

**Usage:** Use this command to view the detailed configuration of a specific LLM.

---

#### `/llm help`
**Description:** Provides help information about bot commands and LLM interaction.

**Arguments:** None

**Usage:** Use this command to get an overview of available commands and how to interact with LLMs.

---

#### `/llm set_simulator`
**Description:** Sets the LLM for simulating responses.

**Arguments:**
- `name`: Name of the LLM to use as simulator (required)

**Usage:** Use this command to designate an LLM as the simulator for natural conversation flow. See the 
[simulator section](#simulator) for more info.

---

#### `/llm set_simulator_channel`
**Description:** Sets the channel for viewing raw simulator responses.

**Arguments:**
- `channel`: The text channel to use for simulator responses (required)

**Usage:** Use this command to specify a channel where the raw simulator responses will be sent. See the 
[simulator section](#simulator) for more info.

### Simulator

To enable natural replies, you must configure a base model simulator. At present the best choice for this task is
Llama 3.1 405b. Here's an example of how you can do that with 405b on Openrouter:

First, create the base model LLM. It is named `simulator` here by convention.

```
/llm create name:simulator api_base:https://openrouter.ai/api/v1 llm_name:meta-llama/llama-3.1-405b api_key:YOUR_API_KEY_HERE max_tokens:256 message_limit:100 enabled:False instruct_tuned:False
```

Next, set the Discord server's simulator model:

```
/llm set_simulator name:simulator
```

Your simulator has been configured. LLMs are now able to respond without an explicit mention or reply.
You can also, optionally, display the simulated conversations in a
channel of your choice. Sometimes it's interesting to see what the base model thinks you'll say next.

```
/llm set_simulator_channel channel:#example
```

Please note that other providers may not work or may result in bugs. Please report any errors that occur!

## Development

- To run tests: `pytest tests/`

## Note

Ensure that your Discord bot has the necessary permissions in your server, including the ability to read messages,
send responses, and manage webhooks.
