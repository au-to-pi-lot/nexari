from svcs import Container, Registry

registry = Registry()
svc = Container(registry=registry)

import src.services.db
import src.services.discord_clientfrom .channel import ChannelProxy
from .guild import GuildProxy
from .webhook import WebhookProxy

__all__ = ["ChannelProxy", "GuildProxy", "WebhookProxy"]
