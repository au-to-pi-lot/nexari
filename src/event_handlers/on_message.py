import discord


async def on_message(message: discord.Message):
    """
    Called when a message is received.

    Args:
        message (discord.Message): The received message.
    """
    if message.author == self.user:
        return

    await self.process_commands(message)

    guild = message.guild
    channel = message.channel

    llm_handlers = await LLMHandler.get_llm_handlers(guild.id)

    # Set to keep track of which LLMs have been pinged in this message
    pinged_llms = set()

    for llm_handler in llm_handlers:
        if llm_handler.mentioned_in_message(message):
            pinged_llms.add(llm_handler)

    self.typing_sets[channel.id].update(pinged_llms)

    # Process the set
    if not self.typing_locks[channel.id].locked():
        await asyncio.create_task(self.process_typing_set(channel))
