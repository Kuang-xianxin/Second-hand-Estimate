from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    deepseek_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None

    deepseek_model: str = "deepseek-chat"
    qwen_model: str = "qwen-max"
    kimi_model: str = "moonshot-v1-8k"

    deepseek_base_url: str = "https://api.deepseek.com"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    llm_timeout_seconds: int = 30

    database_url: str = "sqlite+aiosqlite:///./guessr.db"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"

    crawl_interval_seconds: int = 300
    max_items_per_query: int = 60
    bargain_threshold: float = 120.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
