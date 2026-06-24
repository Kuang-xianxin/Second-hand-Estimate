from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── LLM API Keys ──
    deepseek_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    doubao_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None
    admin_token: Optional[str] = None

    # ── LLM Models ──
    deepseek_model: str = "deepseek-chat"
    deepseek_vision_model: str = "deepseek-chat"
    qwen_model: str = "qwen-max"
    qwen_vision_model: str = "qwen-vl-max"
    qwen_vision_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    doubao_model: str = "ep-m-20260327193150-m6442"
    doubao_model_display: str = "doubao-seed-2.0-pro"
    doubao_vision_model: str = "ep-m-20260327193150-m6442"
    doubao_vision_model_display: str = "doubao-seed-2.0-pro-vision"
    kimi_model: str = "kimi-k2.6"
    kimi_base_url: str = "https://api.moonshot.cn/v1"

    # ── LLM Endpoints ──
    deepseek_base_url: str = "https://api.deepseek.com"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_vision_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    llm_timeout_seconds: int = 120
    doubao_timeout_seconds: int = 90

    # ── Database / Server ──
    database_url: str = "sqlite+aiosqlite:///./guessr.db"
    redis_url: str = "redis://localhost:6379/0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # ── Production ──
    is_production: bool = False
    site_auth_required: bool = True

    # ── Crawl Core ──
    crawl_enabled: bool = True
    crawl_interval_seconds: int = 300
    crawl_scheduler_mode: str = "embedded"  # "embedded" | "external"
    crawl_stability_mode: bool = False
    crawl_stop_on_risk: bool = True
    crawl_canary_enabled: bool = True
    crawl_canary_keywords: str = ""

    # ── Crawl Concurrency ──
    crawl_concurrency: int = 1
    crawl_concurrency_max: int = 3
    crawl_dynamic_concurrency: bool = False
    crawl_batch_size: int = 1
    crawl_keywords_per_run: int = 1
    crawl_dev_keyword_limit: int = 0

    # ── Crawl Rate / Cooldown ──
    crawl_min_interval_seconds: int = 180
    crawl_failure_cooldown_seconds: int = 1800
    crawl_risk_cooldown_seconds: int = 604800
    crawl_max_cooldown_seconds: int = 2592000
    crawl_failure_rate_threshold: float = 0.5
    crawl_slowdown_delay: float = 5.0

    # ── Items / Crawl Scope ──
    max_items_per_query: int = 60
    max_items_per_crawl_keyword: int = 40
    max_pages_per_query: int = 1

    # ── Bargain ──
    bargain_threshold: float = 120.0

    # ── Auth ──
    app_session_ttl_seconds: int = 86400
    password_reset_enabled: bool = False
    xianyu_auth_soft_expire_hours: int = 720
    xianyu_auth_verify_ttl_seconds: int = 300

    # ── SMTP ──
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    def validate_production(self) -> None:
        """确保生产环境关键配置已设置（external 爬虫模式必需）。"""
        if not self.crawl_enabled:
            return
        if self.crawl_scheduler_mode == "external":
            if self.crawl_min_interval_seconds < 30:
                raise ValueError("crawl_min_interval_seconds 过小（<30s）")

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = False


settings = Settings()
