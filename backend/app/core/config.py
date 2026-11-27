from functools import lru_cache

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Metadados da aplicação
    app_name: str = "Agente de Simulação Tributária - RTC"
    environment: str = "development"
    debug: bool = False

    # Provedor LLM (compatível com OpenAI, Groq ou Ollama local)
    openai_api_key: SecretStr = SecretStr("ollama-local")
    openai_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:7b"
    llm_timeout_seconds: float = 20.0
    max_history_messages: int = 12

    # Infraestrutura Interna Docker
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 900  # 15 minutos (minimização LGPD)
    danfse_ttl_seconds: int = 600  # 10 minutos para download do PDF
    rate_limit_requests: int = 20  # Máximo de requisições por janela
    rate_limit_window_seconds: int = 60

    # Motores Oficiais da Receita Federal
    rfb_regular_url: HttpUrl = "http://localhost:8081/api"
    rfb_simples_url: HttpUrl = "http://localhost:8082/api"
    rfb_danfse_url: HttpUrl = "http://localhost:8083"
    rfb_timeout_seconds: float = 10.0

    # Modelo local para roteamento semântico
    embedding_model_name: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna instância única (singleton) das configurações em memória."""
    return Settings()
