import yaml
from pydantic import BaseModel


class Config(BaseModel):
    bot_token: str
    client_id: str


with open('config.yml', 'r') as config_file:
    config_dict = yaml.safe_load(config_file)
    config = Config(**config_dict)
