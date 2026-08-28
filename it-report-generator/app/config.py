from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./it_reports.db"
    reports_dir: str = "./data/reports"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    report_email_to: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


settings = Settings()
