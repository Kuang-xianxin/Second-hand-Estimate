from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    environment: str = "development"
    deepseek_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    doubao_api_key: Optional[str] = None
    admin_token: Optional[str] = None

    deepseek_model: str = "deepseek-reasoner"
    deepseek_vision_model: str = "deepseek-chat"
    qwen_model: str = "qwen-max"
    qwen_vision_model: str = "qwen-vl-max"
    qwen_vision_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    doubao_model: str = "ep-m-20260327193150-m6442"
    doubao_model_display: str = "doubao-seed-2.0-pro"
    doubao_vision_model: str = "ep-m-20260327193150-m6442"
    doubao_vision_model_display: str = "doubao-seed-2.0-pro-vision"

    deepseek_base_url: str = "https://api.deepseek.com"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_vision_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    llm_timeout_seconds: int = 120
    doubao_timeout_seconds: int = 90

    database_url: str = "sqlite+aiosqlite:///./guessr.db"
    redis_url: str = "redis://localhost:6379/0"
    backend_port: int = 8001
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""
    trusted_hosts: str = "*"
    site_auth_required: bool = False
    password_reset_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_use_tls: bool = True
    app_session_ttl_seconds: int = 604800  # 站内登录态 7 天
    xianyu_auth_verify_ttl_seconds: int = 1800  # 闲鱼授权健康检查缓存 30 分钟
    xianyu_auth_soft_expire_hours: int = 12  # 超过此时间未验证则要求重新校验
    stream_image_analysis_enabled: bool = False  # 流式估价是否启用视觉核查；默认关闭以控制通义视觉调用成本

    # 定时任务
    crawl_interval_seconds: int = 5400  # T0 热门型号爬取间隔（1.5 小时）
    crawl_enabled: bool = False         # 是否启用定时爬取（开发默认关闭，生产 .env 开启）
    initial_crawl_enabled: bool = False # 首次启动是否自动触发全量爬取（仅缓存表为空时；开发默认关闭）
    crawl_scheduler_mode: str = "embedded"  # embedded=Web 进程内 APScheduler，external=独立短命 worker
    crawl_stability_mode: bool = False  # production: one request per run with hard Redis cooldown
    crawl_keywords_per_run: int = 1
    crawl_min_interval_seconds: int = 180
    crawl_coverage_target_seconds: int = 172800
    crawl_failure_cooldown_seconds: int = 1800
    crawl_risk_cooldown_seconds: int = 604800
    crawl_max_cooldown_seconds: int = 2592000

    # 分层爬取间隔
    crawl_interval_t1_seconds: int = 43200   # T1 普通型号间隔（12 小时）
    crawl_interval_t2_seconds: int = 259200  # T2 长尾型号间隔（3 天）
    crawl_t0_enabled: bool = True     # 是否启用 T0 定时爬取
    crawl_t1_enabled: bool = False    # 是否启用 T1 定时爬取（默认关闭，按需开启）
    crawl_t2_enabled: bool = False    # 是否启用 T2 定时爬取（默认关闭，按需开启）

    # 爬取控制
    max_items_per_query: int = 200      # 单个关键词最多爬取商品数
    max_items_per_query_t0: int = 40    # T0 单个关键词最多爬取商品数（够用即停）
    max_pages_per_query: int = 2        # 单个关键词最多翻页数（开发默认 2 页防封）
    max_pages_per_query_t0: int = 2     # T0 翻页数（1-2 页足够 20-40 个有效样本）
    crawl_concurrency: int = 1          # 并发爬取数（开发默认单并发防封）
    crawl_concurrency_max: int = 3      # 动态并发上限
    crawl_batch_size: int = 50          # 每批关键词数量
    crawl_dev_keyword_limit: int = 0    # 开发模式关键词上限（0=不限制，生产 .env 设 0 全量）
    crawl_stop_on_risk: bool = True     # 检测到登录失效/风控时立即熔断，避免继续请求

    # 动态并发控制
    crawl_dynamic_concurrency: bool = True  # 是否启用动态并发（根据失败率自动降速）
    crawl_failure_rate_threshold: float = 0.3  # 失败率超过此阈值时降并发
    crawl_slowdown_delay: float = 10.0        # 降速后的额外延迟（秒）

    # Canary 预检
    crawl_canary_enabled: bool = True   # 是否在每轮爬取前运行 canary 关键词预检
    crawl_canary_keywords: str = "佳能ixus130,索尼t700"  # canary 预检关键词（逗号分隔）

    bargain_threshold: float = 120.0

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins or self.frontend_url
        return [value.strip().rstrip("/") for value in raw.split(",") if value.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [value.strip() for value in self.trusted_hosts.split(",") if value.strip()]

    def validate_production(self) -> None:
        scheduler_mode = self.crawl_scheduler_mode.strip().lower()
        if scheduler_mode not in {"embedded", "external"}:
            raise RuntimeError("Invalid configuration: CRAWL_SCHEDULER_MODE must be embedded or external")

        if not self.is_production:
            return

        errors = []
        if not self.database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
            errors.append("DATABASE_URL must use PostgreSQL")
        if not self.redis_url:
            errors.append("REDIS_URL is required")
        if not self.admin_token or len(self.admin_token) < 32:
            errors.append("ADMIN_TOKEN must be at least 32 characters")
        if not self.site_auth_required:
            errors.append("SITE_AUTH_REQUIRED must be true")
        if not self.cors_origin_list or "*" in self.cors_origin_list:
            errors.append("CORS_ORIGINS/FRONTEND_URL must list explicit origins")
        if self.trusted_host_list == ["*"]:
            errors.append("TRUSTED_HOSTS must list explicit hosts")
        if self.password_reset_enabled and not all(
            [self.smtp_host, self.smtp_from_email]
        ):
            errors.append("SMTP_HOST and SMTP_FROM_EMAIL are required when password reset is enabled")
        if self.crawl_enabled and scheduler_mode != "external":
            errors.append("CRAWL_SCHEDULER_MODE must be external when production crawling is enabled")
        if self.crawl_enabled and not self.crawl_stop_on_risk:
            errors.append("CRAWL_STOP_ON_RISK must be true when production crawling is enabled")
        if self.crawl_enabled and (
            self.crawl_concurrency != 1 or self.crawl_concurrency_max != 1
        ):
            errors.append(
                "CRAWL_CONCURRENCY and CRAWL_CONCURRENCY_MAX must both be 1 "
                "when production crawling is enabled"
            )
        if self.crawl_enabled and not self.crawl_stability_mode:
            errors.append("CRAWL_STABILITY_MODE must be true when production crawling is enabled")
        if self.crawl_enabled and self.crawl_keywords_per_run != 1:
            errors.append("CRAWL_KEYWORDS_PER_RUN must be 1 when production crawling is enabled")
        if self.crawl_enabled and self.max_pages_per_query != 1:
            errors.append("MAX_PAGES_PER_QUERY must be 1 when production crawling is enabled")
        if self.crawl_enabled and self.max_items_per_query_t0 > 20:
            errors.append("MAX_ITEMS_PER_QUERY_T0 must be <= 20 when production crawling is enabled")
        if self.crawl_enabled and self.crawl_dynamic_concurrency:
            errors.append("CRAWL_DYNAMIC_CONCURRENCY must be false when production crawling is enabled")
        if self.crawl_enabled and self.crawl_min_interval_seconds < 180:
            errors.append("CRAWL_MIN_INTERVAL_SECONDS must be >= 180 in production")
        if self.crawl_enabled:
            from app.services.keyword_tier import get_all_model_ids

            model_count = len(get_all_model_ids())
            request_budget = self.crawl_min_interval_seconds * model_count
            if request_budget > int(self.crawl_coverage_target_seconds * 0.75):
                errors.append(
                    "CRAWL_MIN_INTERVAL_SECONDS leaves insufficient runtime margin "
                    f"to attempt {model_count} models within CRAWL_COVERAGE_TARGET_SECONDS"
                )
        if self.crawl_enabled and self.crawl_risk_cooldown_seconds < 604800:
            errors.append("CRAWL_RISK_COOLDOWN_SECONDS must be >= 604800 in production")

        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
