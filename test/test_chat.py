import os
import sys
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Configurar paths
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

# Cargar variables de entorno
load_dotenv(dotenv_path=root_path / '.env')

from core.config import get_config
from core.orchestrator import ChatOrchestrator
from core.handlers import TelegramBotHandler

# Configuración de Logging centralizada
log_dir = root_path / "test" / "logs"
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = log_dir / f"{timestamp}_test_chat.log"

# Desactivar logs de HTTP requests y otros ruidos
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("TestChat")

class LoggingTestHandler(TelegramBotHandler):
    """Handler que registra detalladamente cada paso del chat."""
    
    def __init__(self, chat_orchestrator):
        super().__init__(chat_orchestrator)
        self.initial_context_logged = {}

    async def _process_generic_message(self, update, context, is_photo=False):
        user_id = update.effective_user.id
        ctx = self.service.ctx_manager.get_context(user_id)
        user_text = update.message.text or update.message.caption or ""
        
        # 1. Log inicial por única vez
        if user_id not in self.initial_context_logged:
            logger.info(f"\n{'='*60}\n[ESTRUCTURA INICIAL DEL CONTEXTO]\n{'='*60}")
            logger.info(json.dumps(ctx.dict(), indent=2, ensure_ascii=False))
            logger.info(f"{'='*60}\n")
            self.initial_context_logged[user_id] = True

        # 2. Log de datos dinámicos antes de la respuesta
        logger.info(f"--- PASO DEL CHAT ---")
        logger.info(f"USUARIO: {user_text}")
        
        # Llamar a la lógica original
        await super()._process_generic_message(update, context, is_photo)
        
        # 3. Log de resultados (solo lo que cambia y mensajes)
        last_prompt = self.service.last_prompts.get(user_id)
        
        # Intentamos obtener la última respuesta del historial
        history = self.service.chat_agent.get_chat_history(user_id)
        bot_reply = history[-1].content if history else "(no reply)"

        logger.info(f"BOT: {bot_reply}")
        logger.info(f"MOOD: {ctx.mood}")
        logger.info(f"CLOTHES: {ctx.clothes} (Key: {ctx.clothes_key})")
        logger.info(f"LOCATION: {ctx.location}")
        logger.info(f"PROMPT IMAGEN: {last_prompt}")
        logger.info(f"{'-'*30}\n")

def run_test_chat():
    """Ejecuta el bot de Telegram en modo TEST CHAT con logs filtrados."""
    config = get_config()
    logger.info(f"🚀 TEST CHAT | Log: {log_file.name}\n")

    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

    chat_orchestrator = ChatOrchestrator(
        llm_api_key=config.LLM_API_KEY,
        model_name=config.LLM_MODEL_NAME,
        base_url=config.LLM_BASE_URL,
        replicate_api_token=config.REPLICATE_API_TOKEN,
    )

    bot_handler = LoggingTestHandler(chat_orchestrator)
    
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    
    async def handle_set_rel(update, context):
        """Comando /rel <valor> para definir el nivel de relación manualmente."""
        user_id = update.effective_user.id
        ctx = chat_orchestrator.ctx_manager.get_context(user_id)
        args = context.args
        if not args:
            await update.message.reply_text(f"📊 Relación actual: {ctx.relationship}\nUso: /rel <número>")
            return
        try:
            value = int(args[0])
            ctx.relationship = value
            await update.message.reply_text(f"✅ Relación establecida en: {value}")
            logger.info(f"🔧 RELATIONSHIP SET: {value}")
        except ValueError:
            await update.message.reply_text("❌ Usa un número entero. Ej: /rel 15")

    application.add_handler(CommandHandler('rel', handle_set_rel))
    application.add_handler(CommandHandler('start', bot_handler.handle_start))
    application.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), bot_handler.handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, bot_handler.handle_photo))

    # Manejador de errores para el test
    async def error_handler(update: object, context: object) -> None:
        from telegram.error import Forbidden, NetworkError, TimedOut
        if isinstance(context.error, Forbidden):
            logger.warning("🚫 Bot bloqueado por el usuario.")
        elif isinstance(context.error, (NetworkError, TimedOut)):
            logger.warning(f"🌐 Error de conexión: {context.error}")
        else:
            logger.error(f"🔥 Error: {context.error}", exc_info=context.error)

    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == '__main__':
    run_test_chat()
