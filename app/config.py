from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    database_url: str = "sqlite:///./faceless_pipeline.db"
    env: str = "development"

    # Module 1: Trend finder
    trend_seed_keywords: str = "ai tools,personal finance,productivity hacks"
    youtube_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "faceless-pipeline/0.1"
    reddit_subreddits: str = "todayilearned,LifeProTips,Showerthoughts"

    # Module 2: Script generator
    anthropic_api_key: str = ""
    script_model: str = "claude-sonnet-5"

    # Module 3: Voice generation
    kokoro_voice: str = "af_heart"
    tts_fallback_api_key: str = ""
    tts_fallback_provider: str = "elevenlabs"

    # Module 4: Video assembly
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    ffmpeg_binary: str = "ffmpeg"
    output_dir: str = "./data/videos"

    # Module 5: Review checkpoint
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    # Module 6: Publisher
    youtube_client_secrets_file: str = "./secrets/youtube_client_secret.json"
    youtube_token_file: str = "./secrets/youtube_token.json"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""

    # Module 8: Analytics
    youtube_analytics_token_file: str = "./secrets/youtube_analytics_token.json"

    @property
    def trend_seed_keyword_list(self) -> list[str]:
        return [k.strip() for k in self.trend_seed_keywords.split(",") if k.strip()]

    @property
    def reddit_subreddit_list(self) -> list[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",") if s.strip()]


settings = Settings()
