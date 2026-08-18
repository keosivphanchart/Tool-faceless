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
    newsapi_key: str = ""
    news_country: str = "us"
    news_category: str = ""
    enable_tiktok_trends: bool = True
    tiktok_trending_country: str = "US"

    # Module 2: Script generator
    script_provider: str = "anthropic"  # anthropic | ollama | openai | gemini | groq
    anthropic_api_key: str = ""
    script_model: str = "claude-sonnet-5"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    # Module 3: Voice generation
    kokoro_voice: str = "af_heart"
    tts_fallback_api_key: str = ""
    tts_fallback_provider: str = "elevenlabs"

    # Module 4: Video assembly
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    ffmpeg_timeout_seconds: int = 600
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
    tiktok_api_base_url: str = "https://open.tiktokapis.com"
    tiktok_token_file: str = "./secrets/tiktok_token.json"
    tiktok_redirect_uri: str = "http://localhost:8765/tiktok/callback"
    tiktok_default_privacy_level: str = "SELF_ONLY"  # safest default: visible only to the posting account

    # Module 8: Analytics
    youtube_analytics_token_file: str = "./secrets/youtube_analytics_token.json"

    @property
    def trend_seed_keyword_list(self) -> list[str]:
        return [k.strip() for k in self.trend_seed_keywords.split(",") if k.strip()]

    @property
    def reddit_subreddit_list(self) -> list[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",") if s.strip()]


settings = Settings()
