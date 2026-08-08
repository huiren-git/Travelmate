import os
from typing import Any, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用配置
    app_name: str = "TravelMate"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "DEBUG"

    # ===== 多模型配置 =====
    # 默认模型（目前先写死 DeepSeek，后续再改为配置驱动）
    default_llm_model: str = "deepseek:deepseek-chat"

    # 各提供商 API Key
    openai_api_key: str = ""
    qwen_api_key: str = ""
    deepseek_api_key: str = ""
    moonshot_api_key: str = ""

    # 高德地图
    amap_api_key: str = ""
    
    # 和风天气
    qweather_api_key: str = ""

    # Redis
    redis_url: str = ""
    redis_max_connections: int = 20           # 连接池最大连接数
    redis_socket_timeout: int = 5             # 读写超时（秒）
    redis_socket_connect_timeout: int = 5     # 连接超时（秒）
    redis_protocol: int = 2                   # RESP2 协议（兼容低版本 Redis）

     # 数据库配置
    database_dir: str = os.getenv("DATABASE_DIR", "./data")
    database_filename: str = "checkpoint.db"

    @property
    def database_path(self) -> str:
        """获取完整的数据库文件路径"""
        return str(Path(self.database_dir) / self.database_filename)

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value


settings = Settings()
