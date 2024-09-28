import logging
from typing import List, Optional

from pydantic import BaseModel

from src.proxies import ChannelProxy, LLMProxy

logger = logging.getLogger(__name__)


class MessageData(BaseModel):
    username: str
    content: str


class Simulator:
    def __init__(self):
        pass

    @classmethod
    async def get_next_participant(cls, channel: ChannelProxy) -> Optional[LLMProxy]:
        guild = await channel.get_guild()
        simulator = await guild.get_simulator()

        if not simulator:
            return None

        messages = list(reversed(await channel.history(limit=simulator.message_limit)))
        llms_in_guild = await guild.get_llms()

        last_speaker = messages[-1].author.name if messages else None

        prompt = await simulator.message_formatter.format_simulator(
            messages=messages,
            system_prompt=simulator.system_prompt,
            webhook=None,
            channel=channel,
            users_in_channel=[llm.name for llm in llms_in_guild],
        )

        logger.info(f"Simulating conversation in #{channel.name}...")
        response = await simulator.generate_simulator_response(prompt=prompt)
        response_str = response["choices"][0]["text"]
        logger.info(f"Received simulator response (#{channel.name}): {response_str}")

        # Send raw simulator response to the designated channel if set
        if guild.simulator_channel_id is not None:
            simulator_channel = await ChannelProxy.get(guild.simulator_channel_id)
            if simulator_channel:
                last_message = messages[-1]
                await simulator_channel.send(f"{last_message.jump_url}:\n```\n{response_str}\n```")


        next_user = await simulator.message_formatter.parse_next_user(response_str, last_speaker)

        if next_user is None:
            logger.info("No new speaker found in the response")
            return None

        return await LLMProxy.get_by_name(next_user, channel.guild.id)
