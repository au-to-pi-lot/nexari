from pathlib import Path

APP_NAME = "Nexari"
VERSION = "0.1.0"

DISCORD_MESSAGE_MAX_CHARS = 2000

ROOT_DIR = Path(__file__).parent.parent.resolve()
LOG_DIR = ROOT_DIR / "log"

WEBHOOK_NAME = f"{APP_NAME} Proxy Webhook"
MAX_WEBHOOKS_PER_CHANNEL = 15