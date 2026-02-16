import os
import logging
from typing import Optional
from dataclasses import dataclass

@dataclass
class LangSmithConfig:
    """Configuración opcional de LangSmith para observabilidad."""
    enabled: bool = True
    api_key: Optional[str] = None
    project: str = "telegram-ai-bot"
    endpoint: str = "https://api.smith.langchain.com"

@dataclass
class Config:
    # Telegram
    TELEGRAM_TOKEN: str
    
    # LLM
    LLM_API_KEY: str
    LLM_BASE_URL: str
    LLM_MODEL_NAME: str
    
    # Replicate
    REPLICATE_API_TOKEN: str
    REPLICATE_MODEL_ID: str
    
    # LangSmith (Optional)
    langsmith: LangSmithConfig = None

    @classmethod
    def load_from_env(cls) -> 'Config':
        """Carga y valida la configuración desde variables de entorno."""
        
        # 1. Telegram
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            raise ValueError("Falta TELEGRAM_BOT_TOKEN en .env")

        # 2. LLM (Logic de prioridad: Grok > OpenRouter)
        grok_key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        if grok_key:
            llm_key = grok_key
            # Fallbacks específicos para Grok
            llm_base_url = os.getenv("LLM_BASE_URL", "https://api.x.ai/v1")
            llm_model = os.getenv("LLM_MODEL_NAME", "grok-beta")
        elif openrouter_key:
            llm_key = openrouter_key
            llm_base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
            llm_model = os.getenv("OPENROUTER_MODEL_NAME") or os.getenv("LLM_MODEL_NAME")
        else:
            raise ValueError("Falta API Key del LLM (GROK_API_KEY o OPENROUTER_API_KEY)")

        if not llm_base_url or not llm_model:
            raise ValueError("Faltan configuración de URL o Modelo del LLM")

        # 3. Replicate
        replicate_token = os.getenv("REPLICATE_API_TOKEN")
        replicate_model = os.getenv("REPLICATE_MODEL_ID")
        
        if not replicate_token:
            raise ValueError("Falta REPLICATE_API_TOKEN en .env")
        if not replicate_model:
            raise ValueError("Falta REPLICATE_MODEL_ID en .env")

        # 4. LangSmith (Optional)
        langsmith_api_key = os.getenv("LANGCHAIN_API_KEY")
        langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        
        langsmith_config = LangSmithConfig(
            enabled=langsmith_enabled and bool(langsmith_api_key),
            api_key=langsmith_api_key,
            project=os.getenv("LANGCHAIN_PROJECT", "telegram-ai-bot"),
            endpoint=os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        )

        return cls(
            TELEGRAM_TOKEN=telegram_token,
            LLM_API_KEY=llm_key,
            LLM_BASE_URL=llm_base_url,
            LLM_MODEL_NAME=llm_model,
            REPLICATE_API_TOKEN=replicate_token,
            REPLICATE_MODEL_ID=replicate_model,
            langsmith=langsmith_config
        )


def setup_langsmith(config: 'Config') -> None:
    """
    Configura LangSmith estableciendo las variables de entorno necesarias.
    Debe llamarse ANTES de importar cualquier módulo de LangChain.
    """
    if not config.langsmith or not config.langsmith.enabled:
        logging.info("LangSmith: Deshabilitado")
        return
    
    # Establecer variables de entorno para LangChain
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = config.langsmith.api_key
    os.environ["LANGCHAIN_PROJECT"] = config.langsmith.project
    os.environ["LANGCHAIN_ENDPOINT"] = config.langsmith.endpoint
    
    logging.info(f"LangSmith: Habilitado (Proyecto: {config.langsmith.project})")


def get_config() -> Config:
    """Carga la configuración desde el entorno."""
    return Config.load_from_env()
