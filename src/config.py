import yaml
from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    bot_token: str
    client_id: str
    database_url: str
    openrouter_api_key: str

    # noinspection PyNestedDecorators
    @field_validator("client_id", mode="before")
    @classmethod
    def transform_client_id_to_str(cls, value) -> str:
        return str(value)


with open("config.yml", "r") as config_file:
    config_dict = yaml.safe_load(config_file)
    config = Config(**config_dict)
