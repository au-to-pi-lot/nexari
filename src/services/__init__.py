from svcs import Container, Registry

registry = Registry()
svc = Container(registry=registry)

import src.services.db
import src.services.discord_client