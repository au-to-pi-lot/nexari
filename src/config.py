from pydantic import field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    bot_token: str
    client_id: str
    database_url: str

    # noinspection PyNestedDecorators
    @field_validator("client_id", mode="before")
    @classmethod
    def transform_client_id_to_str(cls, value) -> str:
        return str(value)

    class Config:
        env_prefix = ""
        case_sensitive = False


config = Config()
