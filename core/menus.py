import base64
import io
import json
import logging
import uuid
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from .context import ContextManager

# Opciones de menú (Sincronizadas con characters.json)
CHARACTER_OPTIONS = {
    "realistic": {
        "sofia": {
            "id": "sofia",
            "name": "Sofia",
            "icon": "🔥",
            "short": "Extrovertida, sensual y magnética",
            "detail": "Rubia, ojos azules y piel bronceada",
        },
    },
    "medieval_fantasy": {},
    "sci_fi": {},
}

# Iconos por defecto para escenarios (si no están en el JSON)
SCENARIO_ICONS = {
    "rooftop": "🌃",
    "library": "📚",
    "beach": "🏖️",
    "city": "🏙️",
    "cafe": "☕",
    "cozy": "🏠",
    "club": "💃",
    "road": "🛣️"
}

START_CONTENT_PATH = Path(__file__).resolve().parent.parent / "assets" / "world_types"
WORLD_TYPES_PATH = START_CONTENT_PATH / "world_types.json"
_START_CONTENT_CACHE = None
_WORLD_TYPES_CACHE = None


def _load_start_content() -> dict:
    global _START_CONTENT_CACHE
    if _START_CONTENT_CACHE is not None:
        return _START_CONTENT_CACHE
    if not START_CONTENT_PATH.exists():
        logging.warning(f"World types directory not found: {START_CONTENT_PATH}")
        _START_CONTENT_CACHE = {}
        return _START_CONTENT_CACHE
    try:
        characters_data = {}
        
        # Cargamos world_types.json para saber qué carpetas buscar
        world_types_config = _load_world_types()
        
        # Para cada tipo de mundo configurado
        for world_key, world_info in world_types_config.items():
            folder_name = world_info.get("folder", world_key)
            world_dir = START_CONTENT_PATH / folder_name
            
            if world_dir.exists() and world_dir.is_dir():
                char_dir = world_dir / "characters"
                if char_dir.exists() and char_dir.is_dir():
                    # Buscamos cada archivo .json de personaje en la subcarpeta characters
                    for char_file in char_dir.glob("*.json"):
                        char_key = char_file.stem
                        char_info = json.loads(char_file.read_text(encoding="utf-8"))
                        
                        scenario_keys = char_info.get("scenarios", [])
                        if isinstance(scenario_keys, list):
                            char_info["scenarios"] = {}
                            for s_id in scenario_keys:
                                desc_path = Path(__file__).resolve().parent.parent / "assets" / "scenarios" / s_id / "description.json"
                                img_path = Path("assets") / "scenarios" / s_id / "imagen.png"
                                
                                if desc_path.exists():
                                    s_data = json.loads(desc_path.read_text(encoding="utf-8"))
                                    # Validar que el escenario pertenece a este personaje
                                    if s_data.get("character") == char_key:
                                        s_data["image_path"] = str(img_path)
                                        # También guardar la ruta del video inicial
                                        video_path = Path("assets") / "scenarios" / s_id / "initial_image.mp4"
                                        s_data["video_path"] = str(video_path)
                                        char_info["scenarios"][s_id] = s_data
                                    else:
                                        logging.warning(f"Scenario {s_id} does not belong to {char_key}")
                                else:
                                    logging.warning(f"Scenario description not found: {desc_path}")
                        
                        characters_data[char_key] = char_info
        
        _START_CONTENT_CACHE = characters_data
        return _START_CONTENT_CACHE
    except Exception as exc:
        logging.error(f"Failed to load characters from world_types directory: {exc}")
        _START_CONTENT_CACHE = {}
        return _START_CONTENT_CACHE


def _load_world_types() -> dict:
    global _WORLD_TYPES_CACHE
    if _WORLD_TYPES_CACHE is not None:
        return _WORLD_TYPES_CACHE
    if not WORLD_TYPES_PATH.exists():
        logging.warning(f"World types file not found: {WORLD_TYPES_PATH}")
        _WORLD_TYPES_CACHE = {}
        return _WORLD_TYPES_CACHE
    try:
        data = json.loads(WORLD_TYPES_PATH.read_text(encoding="utf-8"))
        _WORLD_TYPES_CACHE = data.get("world_types", {})
        return _WORLD_TYPES_CACHE
    except Exception as exc:
        logging.error(f"Failed to load world types JSON: {exc}")
        _WORLD_TYPES_CACHE = {}
        return _WORLD_TYPES_CACHE


WORLD_TYPE_ICONS = {
    "realistic": "🌍",
    "medieval_fantasy": "⚔️",
    "sci_fi": "🚀",
}


def _get_start_entry(character_key: str, scenario_id: str) -> dict | None:
    content = _load_start_content()
    character = content.get(character_key, {})
    scenarios = character.get("scenarios", {})
    return scenarios.get(scenario_id)


async def _send_start_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    character_key: str,
    scenario_id: str,
) -> None:
    entry = _get_start_entry(character_key, scenario_id)
    if not entry:
        logging.warning(f"No start content for {character_key}/{scenario_id}")
        return

    message = entry.get("message", "").strip()
    context_text = entry.get("context", "").strip()
    video_path = entry.get("video_path", "").strip()
    image_path = entry.get("image_path", "").strip()
    
    if not message and not video_path and not image_path:
        return

    chat_id = update.effective_chat.id
    base_dir = Path(__file__).resolve().parent.parent
    
    # Formatear el mensaje final con el contexto en tercera persona si existe
    final_text = ""
    if context_text:
        final_text += f"📖 *Contexto:*\n_{context_text}_\n\n"
    
    if message:
        char_name = CHARACTER_OPTIONS.get(character_key, {}).get("name", "Compañera")
        final_text += f"💬 *{char_name}:* {message}"
    elif context_text:
        # Si no hay mensaje pero sí contexto, nos aseguramos de que final_text no termine en \n\n
        final_text = final_text.strip()

    # Prioridad: enviar video si existe, si no enviar imagen
    if video_path:
        v_path = Path(video_path)
        if not v_path.is_absolute():
            v_path = (base_dir / v_path).resolve()
        
        if v_path.exists():
            with v_path.open("rb") as video_file:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=final_text or None,
                    parse_mode='Markdown',
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )
            return
        logging.warning(f"Start video not found: {v_path}")

    # Fallback a imagen si no hay video
    if image_path:
        i_path = Path(image_path)
        if not i_path.is_absolute():
            i_path = (base_dir / i_path).resolve()
        
        # Intentar con initial_image.png si el path original no existe
        if not i_path.exists():
            alt_png = i_path.parent / "initial_image.png"
            if alt_png.exists():
                i_path = alt_png

        if i_path.exists():
            with i_path.open("rb") as image_file:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=image_file,
                    caption=final_text or None,
                    parse_mode='Markdown',
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=60,
                )
            return
        logging.warning(f"Start image not found: {i_path}")

    # Fallback a solo texto
    if final_text:
        await context.bot.send_message(
            chat_id=chat_id, 
            text=final_text,
            parse_mode='Markdown'
        )

CLOTHES_OPTIONS = {
    "c_lingerie": "Lencería Sensual",
    "c_underwear": "Ropa Interior Erótica",
    "c_nude": "Desnuda",
    "c_see_through": "Ropa Transparente",
    "c_normal": "Ropa Normal",
    "c_swimsuit": "Traje de Baño"
}

LOCATION_OPTIONS = {
    "l_bedroom": "Dormitorio Íntimo",
    "l_shower": "Ducha",
    "l_hotel": "Suite de Hotel",
    "l_beach": "Playa Privada",
    "l_living": "Sala de Estar",
    "l_kitchen": "Cocina"
}

async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx_manager: ContextManager):
    """Inicia el flujo de selección con el menú de Personaje."""
    user = update.effective_user
    ctx_manager.reset_context(user.id)

    lines = ["Elige tu compañera:", ""]
    
    keyboard = []
    # Iteramos por mundos para mostrar todos los personajes disponibles
    for world_key, world_chars in CHARACTER_OPTIONS.items():
        for char_key, char_opt in world_chars.items():
            icon = char_opt.get("icon", "👤")
            name = char_opt.get("name", char_key)
            short = char_opt.get("short", "")
            lines.append(f"{icon} {name} — {short}")
            keyboard.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"char_{char_key}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    description_text = "\n".join(lines)
    await context.bot.send_message(
        update.effective_chat.id,
        text=f"👋 Hola, {user.first_name}.\n\n{description_text}",
        reply_markup=reply_markup
    )


async def handle_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx_manager: ContextManager,
    orchestrator,
    chat_agent,
    image_agent,
    img_gen,
):
    """Maneja los callbacks de los botones."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    ctx = ctx_manager.get_context(user_id)

    if data.startswith("char_"):
        char_key = data.replace("char_", "")
        
        # 1. Determinar el mundo del personaje y cargar sus reglas
        world_key = None
        character_config = None
        for w_key, world_chars in CHARACTER_OPTIONS.items():
            if char_key in world_chars:
                world_key = w_key
                character_config = world_chars[char_key]
                break
        
        if not world_key or not character_config:
            await query.edit_message_text(text="Error al seleccionar personaje.")
            return

        # Cargar reglas del mundo automáticamente
        world_types = _load_world_types()
        world_data = world_types.get(world_key, {})
        
        ctx.world_type = world_key
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

        # 2. Cargar escenarios del personaje
        ctx.character = character_config['name']
        content = _load_start_content()
        char_data = content.get(char_key, {})
        scenarios_dict = char_data.get("scenarios", {})
        
        if not scenarios_dict:
            await query.edit_message_text(text="No se encontraron escenarios para este personaje. Intenta de nuevo con /start.")
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
            desc = s_data.get("context", "")[:50] + "..." if len(s_data.get("context", "")) > 50 else s_data.get("context", "")
            
            lines.append(f"{icon} {title} — {desc}")
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {title}",
                    callback_data=f"s_{char_key}_{s_id}",
                )
            ])

        await query.edit_message_text(
            text="\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("s_"):
        # Formato esperado: s_sofia_club
        parts = data.split("_")
        if len(parts) < 3:
            await query.edit_message_text(text="Error en el formato del escenario.")
            return
            
        char_key = parts[1]
        scenario_id = parts[2]
        
        content = _load_start_content()
        char_info = content.get(char_key)
        if not char_info:
            await query.edit_message_text(text="No se encontró el personaje en el archivo de configuración.")
            return
            
        scenario_data = char_info.get("scenarios", {}).get(scenario_id)
        if not scenario_data:
            await query.edit_message_text(text="No se encontró el escenario en el archivo de configuración.")
            return

        # ── Cargar TODA la información del personaje en el contexto ──
        ctx.char_key = char_key
        ctx.char_name = char_info.get("name", "Compañera")
        ctx.personality = char_info.get("personality", "")
        ctx.likes = char_info.get("likes", [])
        ctx.dislikes = char_info.get("dislikes", [])
        ctx.physical_description = char_info.get("appearance", "")
        ctx.outfits = char_info.get("outfits", {})
        ctx.home = char_info.get("home", {})
        
        ctx.character = f"{ctx.char_name} — {ctx.personality}"
        
        loc_key = scenario_data.get("location", "bedroom")
        ctx.scenario = scenario_data.get("title", "Escenario")
        ctx.scenario_context = scenario_data.get("context", "")
        ctx.initial_action = scenario_data.get("initial_action", "")
        ctx.location = loc_key
        
        outfit_key = scenario_data.get("clothes", "casual")
        ctx.clothes_key = outfit_key
        ctx.clothes = ctx.outfits.get(outfit_key, outfit_key)
        
        ctx.mood = scenario_data.get("initial_mood", char_info.get("default_mood", "cheerful"))
        
        if scenario_data.get("initial_image_prompt"):
            orchestrator.last_prompts[user_id] = scenario_data.get("initial_image_prompt")

        ctx.is_setup_complete = True
        await _send_start_content(update, context, char_key, scenario_id)
        
        # Obtener icono del mundo
        world_types = _load_world_types()
        world_data = world_types.get(ctx.world_type, {})
        world_icon = WORLD_TYPE_ICONS.get(ctx.world_type, "🌐")

        await query.edit_message_text(
            text=(
                f"✅ Configuración lista.\n"
                f"Mundo: {world_icon} {world_data.get('name', ctx.world_type)}.\n"
                f"Personaje: {ctx.char_name}.\n"
                f"Escenario: {ctx.scenario}.\n\n"
                "Puedes escribir tu mensaje cuando quieras."
            ),
        )
        return

    elif data.startswith("c_"):
        ctx.clothes = CLOTHES_OPTIONS.get(data, "Ropa normal")

        keyboard = [[InlineKeyboardButton(text, callback_data=key)] for key, text in LOCATION_OPTIONS.items()]
        await query.edit_message_text(
            text=(
                f"Personaje: {ctx.character}. "
                f"Escenario: {ctx.scenario}. "
                f"Viste: {ctx.clothes}. 📍 ¿Dónde se encuentra?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        
    elif data.startswith("l_"):
        ctx.location = LOCATION_OPTIONS.get(data, "Lugar desconocido")
        ctx.is_setup_complete = True
        
        await query.edit_message_text(text="✅ Configuración lista. Generando mensaje inicial...")
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Generar mensaje inicial
        initial_message = "Hola, soy nuevo aquí. Preséntate."
        agent_response = await chat_agent.get_response(initial_message, ctx)
        ctx.msg_count += 1
        
        reply_text = agent_response.get("reply", "...")
        # Usar agente especializado en prompts de imagen (contexto + mensaje + respuesta)
        try:
            prompt_for_image = await image_agent.generate_image_prompt(ctx, initial_message, reply_text)
            if prompt_for_image:
                image_bytes = await img_gen.generate_image(prompt_for_image)
                # Store data-URI for the animate button (animator needs URL / data-URI)
                animate_key = uuid.uuid4().hex[:12]
                data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
                orchestrator.store_image_for_animate(animate_key, data_uri)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎬 Animar", callback_data=f"animate_{animate_key}")]
                ])
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
                photo_file = io.BytesIO(image_bytes)
                photo_file.name = "image.png"
                if len(reply_text) <= 1000:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo_file,
                        caption=reply_text,
                        reply_markup=keyboard,
                        read_timeout=60, write_timeout=60, connect_timeout=60
                    )
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)
                    photo_file.seek(0)
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo_file,
                        reply_markup=keyboard,
                        read_timeout=60, write_timeout=60, connect_timeout=60
                    )
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)
        except Exception as e:
            logging.error(f"Error generando o enviando imagen: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)
