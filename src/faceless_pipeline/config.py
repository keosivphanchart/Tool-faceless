from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    database_url: str = "sqlite:///./faceless_pipeline.db"
    env: str = "development"

    # Dashboard auth - a single admin password gating the whole API
    # behind a login screen + session cookie. Empty (the default) means
    # auth is OFF: every endpoint is open, same as before this existed -
    # fine for local dev, never for anything reachable beyond localhost.
    # Set both before deploying anywhere real.
    dashboard_password: str = ""
    # Signs the session cookie. Empty means a random key is generated at
    # process startup instead (sessions just don't survive a restart,
    # which is fine for a single-password admin session).
    dashboard_session_secret: str = ""

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
    youtube_redirect_uri: str = "http://localhost:8000/api/publish/accounts/youtube/callback"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_api_base_url: str = "https://open.tiktokapis.com"
    tiktok_token_file: str = "./secrets/tiktok_token.json"
    tiktok_redirect_uri: str = "http://localhost:8000/api/publish/accounts/tiktok/callback"
    tiktok_default_privacy_level: str = "SELF_ONLY"  # safest default: visible only to the posting account
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_api_base_url: str = "https://graph.facebook.com/v19.0"
    instagram_token_file: str = "./secrets/instagram_token.json"
    instagram_redirect_uri: str = "http://localhost:8000/api/publish/accounts/instagram/callback"
    # Instagram's Content Publishing API fetches the video from a URL you
    # give it rather than accepting a direct upload (unlike YouTube/TikTok)
    # - this has to be the backend's own publicly reachable origin (the
    # one serving GET /media) for that fetch to succeed. Empty = Instagram
    # publishing is unavailable, since localhost isn't fetchable from
    # Meta's servers.
    public_base_url: str = ""
    # Where the dashboard is served from - the connect flow redirects the
    # browser back here (to /settings) once YouTube/TikTok/Instagram OAuth
    # finishes.
    dashboard_url: str = "http://localhost:5173"

    # Module 8: Analytics
    youtube_analytics_token_file: str = "./secrets/youtube_analytics_token.json"

    # Automation — all opt-in / off by default, so the pipeline's existing
    # "one mandatory human checkpoint" behavior is unchanged unless you
    # deliberately turn one of these on.
    auto_generate_enabled: bool = False
    auto_generate_count: int = 1
    auto_generate_min_score: float = 0.0
    auto_generate_style: str = "explainer"
    auto_generate_length_variant: str = "30s"

    auto_trend_finder_enabled: bool = False
    auto_trend_finder_interval_hours: int = 24

    auto_approve_enabled: bool = False
    auto_approve_min_audio_seconds: float = 3.0

    ab_test_enabled: bool = False
    ab_test_styles: str = "explainer,listicle,story,hot_take"

    health_check_interval_minutes: int = 30

    digest_enabled: bool = False
    digest_interval_hours: int = 24

    daily_cost_budget_usd: float = 0.0  # 0 = unlimited
    monthly_cost_budget_usd: float = 0.0  # 0 = unlimited

    cleanup_enabled: bool = False
    cleanup_retention_days: int = 30
    cleanup_interval_hours: int = 24

    retry_max_attempts: int = 3
    retry_backoff_seconds: int = 30

    @property
    def trend_seed_keyword_list(self) -> list[str]:
        return [k.strip() for k in self.trend_seed_keywords.split(",") if k.strip()]

    @property
    def reddit_subreddit_list(self) -> list[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",") if s.strip()]

    @property
    def ab_test_style_list(self) -> list[str]:
        return [s.strip() for s in self.ab_test_styles.split(",") if s.strip()]


settings = Settings()
