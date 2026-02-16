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
log_file = log_dir / f"{timestamp}_test_conversation.log"

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

logger = logging.getLogger("TestConversation")

class NoImageLoggingOrchestrator(ChatOrchestrator):
    """Orquestador que NO genera imágenes pero registra los prompts que se hubieran usado."""
    
    async def maybe_generate_image(self, user_id, user_message, reply_text):
        ctx = self.ctx_manager.get_context(user_id)
        conversation_history = self.chat_agent.get_chat_history(user_id)
        last_prompt = self.last_prompts.get(user_id)
        
        try:
            prompt_for_image = await self.image_agent.generate_image_prompt(
                ctx, 
                user_message, 
                reply_text,
                conversation_history=conversation_history,
                last_prompt=last_prompt
            )
            self.last_prompts[user_id] = prompt_for_image
        except Exception as e:
            logger.error(f"Error calculando prompt: {e}")
            
        return None

class LoggingConversationHandler(TelegramBotHandler):
    """Handler que registra detalladamente cada paso del chat (sin enviar imágenes)."""
    
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
        logger.info(f"--- PASO DEL CHAT (SOLO TEXTO) ---")
        logger.info(f"USUARIO: {user_text}")
        
        await super()._process_generic_message(update, context, is_photo)
        
        # 3. Log de resultados (solo lo que cambia y mensajes)
        last_prompt = self.service.last_prompts.get(user_id)
        history = self.service.chat_agent.get_chat_history(user_id)
        bot_reply = history[-1].content if history else "(no reply)"

        logger.info(f"BOT: {bot_reply}")
        logger.info(f"MOOD: {ctx.mood}")
        logger.info(f"CLOTHES: {ctx.clothes} (Key: {ctx.clothes_key})")
        logger.info(f"LOCATION: {ctx.location}")
        logger.info(f"PROMPT CALCULADO: {last_prompt}")
        logger.info(f"{'-'*30}\n")

def run_test_conversation():
    """Ejecuta el bot de Telegram en modo TEST CONVERSATION con logs filtrados."""
    config = get_config()
    logger.info(f"🚀 TEST CONVERSATION | Log: {log_file.name}\n")

    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

    chat_orchestrator = NoImageLoggingOrchestrator(
        llm_api_key=config.LLM_API_KEY,
        model_name=config.LLM_MODEL_NAME,
        base_url=config.LLM_BASE_URL,
        replicate_api_token=config.REPLICATE_API_TOKEN,
    )

    bot_handler = LoggingConversationHandler(chat_orchestrator)
    
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    
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
    run_test_conversation()
