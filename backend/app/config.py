from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
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

    # 定时任务
    crawl_interval_seconds: int = 5400  # 全量爬取间隔（1.5 小时）
    crawl_enabled: bool = False         # 是否启用定时爬取（开发默认关闭，生产 .env 开启）
    initial_crawl_enabled: bool = False # 首次启动是否自动触发全量爬取（仅缓存表为空时；开发默认关闭）

    # 爬取控制
    max_items_per_query: int = 200      # 单个关键词最多爬取商品数
    max_pages_per_query: int = 2        # 单个关键词最多翻页数（开发默认 2 页防封）
    crawl_concurrency: int = 1          # 并发爬取数（开发默认单并发防封）
    crawl_batch_size: int = 50          # 每批关键词数量
    crawl_dev_keyword_limit: int = 0    # 开发模式关键词上限（0=不限制，生产 .env 设 0 全量）
    crawl_stop_on_risk: bool = True     # 检测到登录失效/风控时立即熔断，避免继续请求

    bargain_threshold: float = 120.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
