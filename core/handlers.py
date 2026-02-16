import io
import os
import json
import time
import logging
import uuid
import base64
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import ContextTypes

from .orchestrator import ChatOrchestrator
from .menus import (
    start_menu,
    handle_selection,
    _load_start_content,
    _load_world_types,
    _send_start_content,
    CHARACTER_OPTIONS,
    WORLD_TYPE_ICONS,
    SCENARIO_ICONS,
)

class TelegramBotHandler:
    """
    Capa de Presentación / Adaptador para Telegram.
    Solo se encarga de:
    1. Recibir Updates de Telegram
    2. Llamar al Orchestrator
    3. Gestionar lógica de imágenes con contador
    4. Formatear y enviar respuestas a Telegram
    """

    def __init__(self, chat_orchestrator: ChatOrchestrator):
        self.service = chat_orchestrator
        self._last_msg_ts: dict[int, float] = {}
        self._spam_score: dict[int, int] = {}
        self.test_mode = os.getenv("BOT_TEST_MODE", "false").lower() in ("1", "true", "yes", "on")
        self.miniapp_url = os.getenv("TELEGRAM_MINIAPP_URL", "").strip()
        
    def _is_rate_limited(self, user_id: int) -> bool:
        """Control simple anti-spam para evitar respuestas superpuestas y pérdida de inmersión."""
        now = time.time()
        last = self._last_msg_ts.get(user_id, 0.0)
        delta = now - last if last else 999.0

        score = self._spam_score.get(user_id, 0)
        if delta < 0.9:
            score += 1
        else:
            score = max(0, score - 1)

        self._last_msg_ts[user_id] = now
        self._spam_score[user_id] = score

        return score >= 3

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /start iniciando el menú."""
        # Accedemos al manager a través del servicio para los menús legacy
        # (Idealmente refactorizaríamos menus.py también, pero por ahora mantenemos compatibilidad)
        await start_menu(update, context, self.service.ctx_manager)

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /help mostrando la guía de uso."""
        user_id = update.effective_user.id
        ctx = self.service.ctx_manager.get_context(user_id)
        
        help_text = f"""
🤖 *Guía de Uso del Bot*

*Tu Energía Actual:* {ctx.energy} ⚡

*Comandos:*
• `/start` - Reiniciar configuración
• `/status` - Ver energía y estadísticas
• `/help` - Ver esta guía
• `/give_me_energy` - Recargar energía (Simulación)
• `/setrel <valor>` - Fijar relación (debug)
• `/miniapp` - Abrir selector visual de personaje
• `/info` - Info técnica (solo test mode)

*Costos de Energía:*
• Mensaje: 1 ⚡
• Imagen: 3 ⚡
• Animación: 40 ⚡
"""
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=help_text,
            parse_mode='Markdown'
        )

    async def handle_checkpoint(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /checkpoint para guardar el estado de la conversación (premium)."""
        user_id = update.effective_user.id

        # Verificar si el usuario tiene setup completo
        ctx = self.service.ctx_manager.get_context(user_id)
        if not ctx.is_setup_complete:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Primero debes completar la configuración con /start antes de guardar un checkpoint."
            )
            return

        # Aquí iría la lógica para guardar el checkpoint (premium feature)
        # Por ahora, solo mostramos un mensaje indicando que es premium
        checkpoint_message = """
💾 *Checkpoint - Función Premium*

Esta función permite guardar el estado actual de tu conversación para continuar más tarde.

*Estado actual guardado:*
• Ropa: {ctx.clothes}
• Ubicación: {ctx.location}
• Mensajes: {ctx.msg_count}

🔒 *Esta es una función premium.* Para acceder, contacta con el administrador o actualiza tu plan.

¿Te gustaría solicitar acceso premium?
        """.format(ctx=ctx)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=checkpoint_message,
            parse_mode='Markdown'
        )

    async def handle_give_me_energy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /give_me_energy para solicitar energía extra."""
        user_id = update.effective_user.id
        ctx = self.service.ctx_manager.get_context(user_id)

        # Si el usuario hace clic en el comando, le damos un poco de energía para probar (simulación)
        # En producción esto sería a través de pagos o anuncios
        ctx.add_energy(50)

        # Mostrar estado actual de energía y opciones
        energy_message = """
⚡ *Energía Actualizada*

Se han añadido *50* unidades de energía a tu cuenta (Simulación).

*Tu Energía:* *{ctx.energy}* ⚡

*Costos:*
• 1 Mensaje: *1* ⚡
• 1 Mensaje + Imagen: *3* ⚡
• 1 Animación: *40* ⚡

Usa `/status` para consultar tu energía en cualquier momento.
        """.format(ctx=ctx)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=energy_message,
            parse_mode='Markdown'
        )

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /status para ver la energía restante."""
        user_id = update.effective_user.id
        ctx = self.service.ctx_manager.get_context(user_id)
        
        status_text = (
            "🔋 *Estado de sesión*\n\n"
            f"Energía disponible: *{ctx.energy}* ⚡\n"
            f"Mensajes enviados: {ctx.msg_count}\n"
            f"Mood actual: {ctx.mood}\n"
            f"Relación: {ctx.relationship}\n"
            f"Lugar: {ctx.location or '—'}"
        )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=status_text,
            parse_mode='Markdown'
        )

    async def handle_setrel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando admin/debug para fijar relación absoluta: /setrel 20"""
        user_id = update.effective_user.id
        ctx = self.service.ctx_manager.get_context(user_id)

        if not context.args:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Uso: /setrel <valor>  (ej: /setrel 20)",
            )
            return

        try:
            value = int(context.args[0])
        except ValueError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="El valor debe ser un número entero. Ej: /setrel 20",
            )
            return

        ctx.set_relationship(value)
        self.service.ctx_manager.save_contexts()

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Relación fijada en {ctx.relationship}",
        )

    async def handle_miniapp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Abre la miniapp de selección de personajes en Telegram."""
        chat_id = update.effective_chat.id

        if not self.miniapp_url:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Falta configurar TELEGRAM_MINIAPP_URL en el entorno.",
            )
            return

        # Botón principal para abrir la miniapp
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("🎭 Abrir selector de personaje", web_app=WebAppInfo(url=self.miniapp_url))]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="Abre la miniapp y elige personaje.",
            reply_markup=kb,
        )

    async def handle_web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Recibe payload JSON de Telegram Mini App y aplica selección de personaje/escenario."""
        if not update.message or not update.message.web_app_data:
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        payload_raw = update.message.web_app_data.data or ""

        try:
            payload = json.loads(payload_raw)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text="❌ Datos inválidos de la miniapp.")
            return

        event_type = str(payload.get("type", "")).strip()
        if event_type not in {"select_character", "select_character_scenario"}:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Evento de miniapp no soportado.")
            return

        char_key = str(payload.get("character", "")).strip().lower()
        if not char_key:
            await context.bot.send_message(chat_id=chat_id, text="❌ No se recibió personaje.")
            return

        # Localizar mundo/personaje
        world_key = None
        character_config = None
        for w_key, world_chars in CHARACTER_OPTIONS.items():
            if char_key in world_chars:
                world_key = w_key
                character_config = world_chars[char_key]
                break

        if not world_key or not character_config:
            await context.bot.send_message(chat_id=chat_id, text="❌ Personaje no disponible.")
            return

        ctx = self.service.ctx_manager.get_context(user_id)
        ctx.char_key = char_key
        ctx.character = character_config.get("name", char_key)
        ctx.world_type = world_key

        # Cargar contexto de mundo
        world_types = _load_world_types()
        world_data = world_types.get(world_key, {})
        if world_data:
            allowed = "\n".join(f"  ✓ {item}" for item in world_data.get("allowed", []))
            forbidden = "\n".join(f"  ✗ {item}" for item in world_data.get("forbidden", []))
            redirect = world_data.get("redirect_behavior", "")
            ctx.world_rules = (
                f"TIPO DE MUNDO: {world_data.get('name', world_key)}\n"
                f"DESCRIPCIÓN: {world_data.get('description', '')}\n\n"
                f"LO QUE EXISTE Y ESTÁ PERMITIDO:\n{allowed}\n\n"
                f"LO QUE NO EXISTE Y ESTÁ PROHIBIDO:\n{forbidden}\n\n"
                f"CÓMO REDIRIGIR PROPUESTAS IMPOSIBLES:\n{redirect}"
            )

        content = _load_start_content()
        char_data = content.get(char_key, {})
        scenarios_dict = char_data.get("scenarios", {})

        # Modo legacy: solo personaje -> mostrar escenarios como antes.
        if event_type == "select_character":
            if not scenarios_dict:
                self.service.ctx_manager.save_contexts()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Personaje seleccionado: {ctx.character}.\n⚠️ No hay escenarios disponibles para este personaje.",
                )
                return

            lines = [
                f"Personaje: {ctx.character}",
                f"Mundo: {WORLD_TYPE_ICONS.get(world_key, '🌐')} {world_data.get('name', world_key)}",
                "",
                "Elige un escenario:",
                "",
            ]
            keyboard = []
            for s_id, s_data in scenarios_dict.items():
                icon = SCENARIO_ICONS.get(s_id, "📍")
                title = s_data.get("title", s_id.capitalize())
                desc_raw = s_data.get("context", "")
                desc = desc_raw[:50] + "..." if len(desc_raw) > 50 else desc_raw
                lines.append(f"{icon} {title} — {desc}")
                keyboard.append([InlineKeyboardButton(f"{icon} {title}", callback_data=f"s_{char_key}_{s_id}")])

            self.service.ctx_manager.save_contexts()
            await context.bot.send_message(
                chat_id=chat_id,
                text="\n".join(lines),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # Nuevo modo: personaje + escenario en miniapp, iniciar chat directo.
        scenario_id = str(payload.get("scenario", "")).strip().lower()
        if not scenario_id:
            await context.bot.send_message(chat_id=chat_id, text="❌ No se recibió escenario.")
            return

        scenario_data = scenarios_dict.get(scenario_id)
        if not scenario_data:
            await context.bot.send_message(chat_id=chat_id, text="❌ Escenario no disponible para este personaje.")
            return

        # Cargar toda la info del personaje en contexto
        ctx.char_name = char_data.get("name", ctx.character)
        ctx.personality = char_data.get("personality", "")
        ctx.likes = char_data.get("likes", [])
        ctx.dislikes = char_data.get("dislikes", [])
        ctx.physical_description = char_data.get("appearance", "")
        ctx.outfits = char_data.get("outfits", {})
        ctx.home = char_data.get("home", {})

        ctx.character = f"{ctx.char_name} — {ctx.personality}"

        loc_key = scenario_data.get("location", "bedroom")
        ctx.scenario = scenario_data.get("title", "Escenario")
        ctx.scenario_context = scenario_data.get("context", "")
        ctx.initial_action = scenario_data.get("initial_action", "")
        ctx.location = loc_key

        outfit_key = scenario_data.get("clothes", "casual")
        ctx.clothes_key = outfit_key
        ctx.clothes = ctx.outfits.get(outfit_key, outfit_key)

        ctx.mood = scenario_data.get("initial_mood", char_data.get("default_mood", "cheerful"))

        if scenario_data.get("initial_image_prompt"):
            self.service.last_prompts[user_id] = scenario_data.get("initial_image_prompt")
            if hasattr(self.service, "_save_last_prompts"):
                self.service._save_last_prompts()

        ctx.is_setup_complete = True
        self.service.ctx_manager.save_contexts()

        await _send_start_content(update, context, char_key, scenario_id)

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ Configuración lista.\n"
                f"Mundo: {WORLD_TYPE_ICONS.get(world_key, '🌐')} {world_data.get('name', world_key)}\n"
                f"Personaje: {ctx.char_name}.\n"
                f"Escenario: {ctx.scenario}.\n\n"
                "Puedes escribir tu mensaje cuando quieras."
            ),
        )

    async def handle_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info técnica para debugging en modo test."""
        if not self.test_mode:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="ℹ️ /info está habilitado solo cuando BOT_TEST_MODE=true",
            )
            return

        user_id = update.effective_user.id
        ctx = self.service.ctx_manager.get_context(user_id)

        scene_state = ctx.scene_state or {}
        scene_lines = "\n".join([f"- {k}: {v}" for k, v in scene_state.items()]) or "- (vacío)"
        last_prompt = (self.service.last_prompts.get(user_id) or "")
        last_prompt_preview = (last_prompt[:220] + "...") if len(last_prompt) > 220 else last_prompt

        interval = self.service._dynamic_image_interval(ctx)

        info_text = (
            "🧪 INFO (TEST MODE)\n\n"
            f"- user_id: {user_id}\n"
            f"- setup_complete: {ctx.is_setup_complete}\n"
            f"- world_type: {ctx.world_type or '-'}\n"
            f"- character: {ctx.char_name or ctx.character or '-'}\n"
            f"- location: {ctx.location or '-'}\n"
            f"- mood: {ctx.mood}\n"
            f"- relationship: {ctx.relationship}\n"
            f"- energy: {ctx.energy}\n"
            f"- msg_count: {ctx.msg_count}\n"
            f"- image_interval_policy: {interval}\n"
            f"- spam_score: {self._spam_score.get(user_id, 0)}\n\n"
            "scene_state:\n"
            f"{scene_lines}\n\n"
            "last_prompt (preview):\n"
            f"{last_prompt_preview or '-'}"
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=info_text,
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja las selecciones del menú y el botón Animar."""
        query = update.callback_query
        data = query.data or ""

        if data.startswith("animate_"):
            await self._handle_animate_callback(update, context, data)
            return
        await handle_selection(
            update,
            context,
            self.service.ctx_manager,
            self.service,
            self.service.chat_agent,
            self.service.image_agent,
            self.service.img_gen,
        )
        self.service.ctx_manager.save_contexts()

    async def _handle_animate_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Anima la imagen asociada al botón y envía el video."""
        key = data[len("animate_"):].strip()
        cached = self.service.get_image_for_animate(key)
        if not cached:
            await update.callback_query.answer("Esta imagen ya no está disponible para animar.", show_alert=True)
            return
        
        image_url, image_prompt = cached
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        try:
            await update.callback_query.answer("Animando imagen... Puede tardar unos minutos.")
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_video")
            
            # Usar orquestador para validar energía y animar (el agente genera la prompt de animación)
            video_result = await self.service.animate_image_with_energy(user_id, image_url, image_prompt=image_prompt)

            if isinstance(video_result, (bytes, bytearray)):
                video_file = io.BytesIO(video_result)
                video_file.name = "animation.mp4"
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )
            else:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_result,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )
        except Exception as e:
            if str(e) == "NO_ENERGY":
                await update.callback_query.answer("⚠️ No tienes suficiente energía (requieres 40 ⚡). Usa /give_me_energy.", show_alert=True)
            else:
                logging.error(f"Error animando imagen: {e}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ No pude animar la imagen: {str(e)}",
                )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa mensajes de texto del usuario."""
        await self._process_generic_message(update, context)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa mensajes que contienen fotos."""
        await self._process_generic_message(update, context, is_photo=True)

    async def _process_generic_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, is_photo: bool = False):
        """Lógica común para procesar texto y fotos."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        text = update.message.text or update.message.caption or ""
        image_data_uri = None

        if self._is_rate_limited(user_id):
            await context.bot.send_message(
                chat_id=chat_id,
                text="Voy contigo, pero dame un segundo para responder bien ✨"
            )
            return

        try:
            if is_photo and update.message.photo:
                # Feedback visual de descarga
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                except Exception:
                    pass
                
                # Obtener la foto de mayor resolución
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                
                # Descargar archivo a memoria
                image_bytes = await file.download_as_bytearray()
                
                # Convertir a Data URI para el LLM
                encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                # Intentar detectar el tipo de archivo (usualmente jpeg en Telegram)
                image_data_uri = f"data:image/jpeg;base64,{encoded_image}"
                
                logging.info(f"📸 Foto procesada como Data URI para usuario {user_id}")

            if not text and not is_photo:
                return

            # 1. Feedback visual inmediato y Placeholder de texto
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            except Exception:
                pass
            
            placeholder_msg = await context.bot.send_message(
                chat_id=chat_id,
                text="💭 _Pensando respuesta..._",
                parse_mode='Markdown'
            )

            # 2. Delegar lógica al servicio para el texto
            response = await self.service.process_user_message(user_id, text, image_url=image_data_uri)

            # Manejar falta de energía
            if response.no_energy:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=placeholder_msg.message_id,
                    text="⚠️ Te has quedado sin energía. Usa /give_me_energy para obtener más. ⚡"
                )
                return

            # Manejar respuesta especial de Setup
            if response.text == "SETUP_REQUIRED":
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=placeholder_msg.message_id,
                    text="⚠️ Por favor usa /start para seleccionar la ropa y el lugar primero."
                )
                return

            # 3. Si va a generar imagen, actualizar placeholder
            ctx = self.service.ctx_manager.get_context(user_id)
            current_count = self.service.image_counters.get(user_id, 0) + 1
            interval = self.service._dynamic_image_interval(ctx)
            scene_shift = self.service._detect_scene_shift(text, response.text)
            should_gen_image = (current_count == 1 or current_count % interval == 0 or scene_shift) and ctx.has_energy(2)

            if should_gen_image:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=placeholder_msg.message_id,
                    text="🎨 _Visualizando la escena para ti..._",
                    parse_mode='Markdown'
                )
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
                except Exception:
                    pass

            # 4. Generar imagen (si corresponde)
            image_bytes = await self.service.maybe_generate_image(
                user_id=user_id,
                user_message=text,
                reply_text=response.text,
            )

            # 5. Preparar respuesta final
            footer = f"\n\n⚡ {ctx.energy}"
            full_text = f"{response.text}{footer}"

            # 6. Enviar resultado y eliminar placeholder
            if image_bytes:
                try:
                    # Store a data-URI and the image prompt for the animator
                    animate_key = uuid.uuid4().hex[:12]
                    data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
                    last_image_prompt = self.service.last_prompts.get(user_id)
                    self.service.store_image_for_animate(animate_key, data_uri, last_image_prompt)
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎬 Animar", callback_data=f"animate_{animate_key}")]
                    ])
                    
                    photo_file = io.BytesIO(image_bytes)
                    photo_file.name = "image.png"
                    
                    # Eliminar placeholder antes de enviar la foto con caption
                    await context.bot.delete_message(chat_id=chat_id, message_id=placeholder_msg.message_id)
                    
                    if len(full_text) <= 1000:
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=photo_file,
                            caption=full_text,
                            reply_markup=keyboard,
                            read_timeout=60, write_timeout=60, connect_timeout=60
                        )
                    else:
                        await context.bot.send_message(chat_id=chat_id, text=full_text)
                        photo_file.seek(0)
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=photo_file,
                            reply_markup=keyboard,
                            read_timeout=60, write_timeout=60, connect_timeout=60
                        )
                except Exception as e:
                    logging.error(f"Error enviando imagen a Telegram: {e}")
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=placeholder_msg.message_id,
                        text=full_text
                    )
            else:
                # Si no hay imagen, simplemente editamos el placeholder con el texto final
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=placeholder_msg.message_id,
                    text=full_text
                )
        except Exception as e:
            from telegram.error import Forbidden
            if isinstance(e, Forbidden):
                logging.warning(f"🚫 Usuario {user_id} bloqueó al bot. Abortando respuesta.")
            else:
                logging.error(f"❌ Error procesando mensaje para {user_id}: {e}", exc_info=True)
