import yaml
from pydantic import BaseModel, Field


class Config(BaseModel):
    bot_token: str
    database_url: str = Field(default="sqlite+aiosqlite:///data.db")


with open('config.yml', 'r') as config_file:
    config_dict = yaml.safe_load(config_file)
    config = Config(**config_dict)
