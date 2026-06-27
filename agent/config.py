"""集中配置：所有可调项从 .env 读，不要在别处硬编码。"""
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5-coder:7b")
MAX_REPAIR_RETRIES = int(os.getenv("MAX_REPAIR_RETRIES", "3"))
TARGET_DB = os.getenv("TARGET_DB", "postgres")
VALIDATE_DB_DSN = os.getenv("VALIDATE_DB_DSN", "postgresql://localhost:5432/migrate_test")

# Ollama 的 OpenAI 兼容端点
OPENAI_BASE_URL = f"{OLLAMA_HOST}/v1"
OPENAI_API_KEY = "ollama"  # Ollama 不校验，占位即可
