#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime

from dotenv import load_dotenv

# Forzar la carga desde el directorio del script para evitar problemas de path
from pathlib import Path
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Importar la lógica de negocio principal
from core.config import get_config, setup_langsmith
from core.orchestrator import ChatOrchestrator
from core.handlers import TelegramBotHandler

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

def run_telegram_bot(config):
    """Configura y ejecuta el bot de Telegram."""
    print(f"Iniciando Bot de Telegram con {config.LLM_MODEL_NAME} en {config.LLM_BASE_URL}...")

    # Importar librerías de Telegram aquí para evitar cargarlas en modo terminal
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

    # Inicializar Capa de Servicio (Lógica de Negocio)
    chat_orchestrator = ChatOrchestrator(
        llm_api_key=config.LLM_API_KEY,
        model_name=config.LLM_MODEL_NAME,
        base_url=config.LLM_BASE_URL,
        replicate_api_token=config.REPLICATE_API_TOKEN,
    )

    # Inicializar Capa de Handlers (Adaptador Telegram)
    bot_handler = TelegramBotHandler(chat_orchestrator)
    
    # Construir aplicación Telegram
    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .connect_timeout(60)
        .build()
    )
    
    # Registrar Rutas/Handlers
    application.add_handler(CommandHandler('start', bot_handler.handle_start))
    application.add_handler(CommandHandler('help', bot_handler.handle_help))
    application.add_handler(CommandHandler('status', bot_handler.handle_status))
    application.add_handler(CommandHandler('checkpoint', bot_handler.handle_checkpoint))
    application.add_handler(CommandHandler('give_me_energy', bot_handler.handle_give_me_energy))
    application.add_handler(CommandHandler('setrel', bot_handler.handle_setrel))
    application.add_handler(CommandHandler('miniapp', bot_handler.handle_miniapp))
    application.add_handler(CommandHandler('info', bot_handler.handle_info))
    application.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, bot_handler.handle_web_app_data))
    # Fallback: algunos clientes pueden enviar texto JSON en vez de web_app_data
    application.add_handler(MessageHandler(filters.Regex(r'^\{.*"type"\s*:\s*"select_character'), bot_handler.handle_web_app_data))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), bot_handler.handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, bot_handler.handle_photo))

    # Manejador de errores global
    async def error_handler(update: object, context: object) -> None:
        from telegram.error import Forbidden, NetworkError, TimedOut, BadRequest
        
        if isinstance(context.error, Forbidden):
            logging.warning(f"🚫 El bot fue bloqueado por el usuario o no tiene permisos.")
        elif isinstance(context.error, TimedOut):
            logging.warning(f"⏱️ Tiempo de espera agotado en la conexión.")
        elif isinstance(context.error, NetworkError):
            logging.warning(f"🌐 Error de red: {context.error}")
        elif isinstance(context.error, BadRequest):
            logging.error(f"❌ Bad Request: {context.error}")
        else:
            logging.error(f"🔥 Error no manejado: {context.error}", exc_info=context.error)

    application.add_error_handler(error_handler)

    # Configurar comandos visibles en el menú de Telegram
    async def set_commands(app):
        from telegram import BotCommand, MenuButtonWebApp, WebAppInfo
        commands = [
            BotCommand("start", "Iniciar configuración y elegir personaje"),
            BotCommand("status", "Ver energía restante"),
            BotCommand("help", "Ver guía de uso"),
            BotCommand("give_me_energy", "Recargar energía"),
            BotCommand("setrel", "Fijar relación (debug)"),
            BotCommand("miniapp", "Abrir selector visual"),
            BotCommand("info", "Info técnica (test mode)"),
        ]
        await app.bot.set_my_commands(commands)

        miniapp_url = os.getenv("TELEGRAM_MINIAPP_URL", "").strip()
        miniapp_ver = os.getenv("TELEGRAM_MINIAPP_VERSION", "20260216")
        if miniapp_url:
            sep = "&" if "?" in miniapp_url else "?"
            versioned_url = f"{miniapp_url}{sep}v={miniapp_ver}"
            try:
                await app.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="🎭 Personajes",
                        web_app=WebAppInfo(url=versioned_url),
                    )
                )
                logging.info(f"✅ Menu button MiniApp configurado: {versioned_url}")
            except Exception as e:
                logging.warning(f"No se pudo configurar menu button MiniApp: {e}")

    # Usar el loop para ejecutar set_commands
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_commands(application))
    
    # Iniciar Loop
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def run_terminal_chat(config):
    """Ejecuta un chat interactivo en la terminal."""

    print(f"Iniciando Chat en Terminal con {config.LLM_MODEL_NAME} en {config.LLM_BASE_URL}...")

    # Inicializar el Servicio de Chat (sin Telegram)
    chat_orchestrator = ChatOrchestrator(
        llm_api_key=config.LLM_API_KEY,
        model_name=config.LLM_MODEL_NAME,
        base_url=config.LLM_BASE_URL,
        replicate_api_token=config.REPLICATE_API_TOKEN,
    )

    user_id = 1 # Usamos un ID fijo para la sesión de terminal
    # Simular el setup inicial si no está completo
    ctx = chat_orchestrator.ctx_manager.get_context(user_id)
    if not ctx.is_setup_complete:
        logging.info("Simulando setup inicial para el chat de terminal...")
        ctx.clothes = "Ropa Normal" # Valor por defecto
        ctx.location = "Sala de Estar" # Valor por defecto
        ctx.mood = "Normal" # Valor por defecto
        ctx.is_setup_complete = True
        ctx.msg_count = 0 # Reiniciar contador de mensajes
        logging.info(f"Contexto inicializado: Clothes={ctx.clothes}, Location={ctx.location}, Mood={ctx.mood}")

    print("Puedes escribir tu mensaje. Presiona Ctrl+C para salir.")
    print("-" * 80)

    # Bucle de Chat Interactivo
    while True:
        image_url = None  # Inicializar al inicio del loop
        try:
            user_input = input("Tú: ")
            if not user_input:
                continue

            # Procesar mensaje del usuario
            response = await chat_orchestrator.process_user_message(user_id, user_input)

            if response.no_energy:
                print("Bot: ⚠️ Te has quedado sin energía. Usa /give_me_energy para obtener más. ⚡")
                continue

            # Lógica de imágenes delegada al orchestrator (returns bytes | None)
            image_bytes = await chat_orchestrator.maybe_generate_image(
                user_id=user_id,
                user_message=user_input,
                reply_text=response.text
            )

            # Mostrar respuesta del bot
            print(f"Bot: {response.text} (Energía restante: {ctx.energy}⚡)")

            if image_bytes:
                out_dir = Path(__file__).parent / "outputs"
                out_dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = out_dir / f"terminal_{ts}.png"
                out_path.write_bytes(image_bytes)
                print(f"🖼️ Imagen generada: {out_path}\n")

        except KeyboardInterrupt:
            print("\n👋 Saliendo del chat. ¡Adiós!")
            break
        except Exception as e:
            logging.error(f"❌ Error inesperado en el chat: {e}")
            print("Hubo un error procesando tu mensaje. Intenta de nuevo.")

def main():
    # 1. Cargar Configuración
    try:
        config = get_config()
    except ValueError as e:
        logging.error(f"❌ Error de Configuración: {e}")
        sys.exit(1)

    # 2. Configurar LangSmith si está habilitado
    setup_langsmith(config)

    # 3. Procesar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Run the Telegram Bot or Terminal Chat.')
    parser.add_argument('--chat-terminal', action='store_true', help='Run in terminal chat mode.')
    args = parser.parse_args()

    # 4. Decidir qué modo ejecutar
    if args.chat_terminal:
        # Ejecutar en modo terminal
        asyncio.run(run_terminal_chat(config))
    else:
        # Ejecutar como bot de Telegram
        run_telegram_bot(config)


if __name__ == '__main__':
    main()
