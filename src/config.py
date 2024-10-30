from pydantic_settings import BaseSettings


class Config(BaseSettings):
    bot_token: str
    client_id: str
    database_url: str

    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"
        env_file_encoding = "utf-8"


config = Config()
