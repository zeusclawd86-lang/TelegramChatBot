"""
Script de prueba para generar imágenes según el contexto seleccionado.
Permite elegir personaje, ropa y lugar, y genera solo la imagen sin necesidad del bot completo.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Añadir raíz del proyecto al path para importar core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar codificación UTF-8 para Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configurar logging para ver qué está pasando
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

from dotenv import load_dotenv
from core.services.image_gen import ImageGenerator
from core.services.animator import ImageAnimator
from core.context import UserContext
from core.agents.image_prompt_agent import ImagePromptAgent

# Cargar variables de entorno
load_dotenv()

# Opciones disponibles (mismas que en menus.py)
CLOTHES_OPTIONS = {
    "1": "Lencería Sensual",
    "2": "Ropa Interior Erótica",
    "3": "Desnuda",
    "4": "Ropa Transparente",
    "5": "Ropa Normal",
    "6": "Traje de Baño"
}

LOCATION_OPTIONS = {
    "1": "Dormitorio Íntimo",
    "2": "Ducha",
    "3": "Suite de Hotel",
    "4": "Playa Privada",
    "5": "Sala de Estar",
    "6": "Cocina"
}

MOOD_OPTIONS = {
    "1": "Aroused",
    "2": "Playful",
    "3": "Dominant",
    "4": "Submissive",
    "5": "Passionate",
    "6": "Teasing",
    "7": "Intense",
    "8": "Relaxed",
    "9": "Normal"
}

POSE_OPTIONS = {
    "1": "Blowjob",
    "2": "Doggy style",
    "3": "Anal",
    "4": "Missionary",
    "5": "69",
    "6": "Cowgirl",
    "7": "Reverse cowgirl"
}

COMPANION_OPTIONS = {
    "1": "dildo",
    "2": "white_male",
    "3": "black_male",
    "4": "blonde_woman",
    "5": "female_companion",
    "6": "tattooed_girl",
    "7": "extra companion"
}

def print_menu(title, options):
    """Imprime un menú de opciones."""
    print(f"\n{title}")
    print("=" * 60)
    for key, value in options.items():
        print(f"  {key}. {value}")
    print("=" * 60)

def get_user_choice(options, prompt_text):
    """Obtiene la elección del usuario."""
    while True:
        choice = input(f"\n{prompt_text} (1-{len(options)}): ").strip()
        if choice in options:
            return options[choice]
        print(f"❌ Opción inválida. Por favor elige un número del 1 al {len(options)}")

def build_image_prompt(context: UserContext, sexual_pose: str, companions: str) -> str:
    """
    Construye un prompt de imagen basado en el contexto.
    Similar a lo que haría el agente LLM pero simplificado para la prueba.
    PROMPT ESTRUCTURADO CON CLUSTERS: formato JSON con clusters organizados.
    """
    # Descripciones simplificadas (máximo 5 términos clave)
    clothes_desc = {
        "Lencería Sensual": "wearing lingerie, bra and panties",
        "Ropa Interior Erótica": "wearing underwear",
        "Desnuda": "nude, no clothes, pussy visible, breasts visible",
        "Ropa Transparente": "wearing see-through clothing",
        "Ropa Normal": "wearing normal clothes",
        "Traje de Baño": "wearing swimsuit"
    }
    
    # Descripciones simplificadas (máximo 5 términos clave)
    location_desc = {
        "Dormitorio Íntimo": "in bedroom, bed visible, dim lighting",
        "Ducha": "in shower, bathroom setting, water visible",
        "Suite de Hotel": "in hotel room, elegant furniture visible",
        "Playa Privada": "on beach, sand visible, ocean in background",
        "Sala de Estar": "in living room, sofa visible",
        "Cocina": "in kitchen, kitchen counter visible"
    }
    
    # Descripciones simplificadas (máximo 5 términos clave)
    mood_desc = {
        "Aroused": "aroused expression, lustful eyes",
        "Playful": "playful expression, teasing smile",
        "Dominant": "dominant expression, confident face",
        "Submissive": "submissive expression, gentle eyes",
        "Passionate": "passionate expression, intense emotion",
        "Teasing": "teasing expression, seductive smile",
        "Intense": "intense expression, focused eyes",
        "Relaxed": "relaxed expression, comfortable face",
        "Normal": "natural expression, casual look"
    }
    
    # Obtener descripciones según el contexto
    cloth = clothes_desc.get(context.clothes, f"wearing {context.clothes.lower() if context.clothes else 'clothes'}")
    loc = location_desc.get(context.location, f"{context.location.lower() if context.location else 'in a room'}")
    mood = mood_desc.get(context.mood, "natural expression")
    
    # Determinar pose según el lugar y el modo sexual seleccionado
    pose_map = {
        "Playa Privada": "sitting on sand",
        "Dormitorio Íntimo": "sitting on bed",
        "Ducha": "standing in shower",
        "Suite de Hotel": "sitting on hotel bed",
        "Sala de Estar": "sitting on sofa",
        "Cocina": "standing in kitchen"
    }
    pose = pose_map.get(context.location, "standing")
    sexual_pose_desc = sexual_pose.lower() if sexual_pose else ""
    if sexual_pose_desc:
        sexual_pose_desc = sexual_pose_desc.replace(" ", " ")
    
    # Construir prompt estructurado con clusters
    character_line = f"{pose}"
    if sexual_pose_desc:
        character_line += f", {sexual_pose_desc}"
    character_line += f", {mood}"
    prompt = f"{{\nEnvironment: {loc}\nClothes: {cloth}\nCharacter: {character_line}\nMood: {mood}"
    if companions:
        prompt += f"\nSexualCompanions: {companions}"
    prompt += "\n}}"
    
    return prompt


def _save_image(image_bytes: bytes, prefix: str = "test_img") -> Path:
    """Save image bytes to the outputs/ directory and return the path."""
    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{prefix}_{ts}.png"
    out_path.write_bytes(image_bytes)
    return out_path


async def test_image_generation():
    """Prueba la generación de una imagen con contexto seleccionado."""
    
    # Obtener credenciales del LLM (Grok)
    GROK_API_KEY = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    
    # Determinar qué API usar
    if GROK_API_KEY:
        LLM_API_KEY = GROK_API_KEY
        LLM_BASE_URL = os.getenv("LLM_BASE_URL")
        LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
    else:
        LLM_API_KEY = OPENROUTER_API_KEY
        LLM_BASE_URL = os.getenv("LLM_BASE_URL")
        LLM_MODEL_NAME = os.getenv("OPENROUTER_MODEL_NAME") or os.getenv("LLM_MODEL_NAME")
    
    if not LLM_API_KEY:
        print("❌ Error: GROK_API_KEY o OPENROUTER_API_KEY no encontrada en .env")
        print("Por favor, asegúrate de tener una de estas API keys en tu archivo .env")
        sys.exit(1)

    if not LLM_BASE_URL or not LLM_MODEL_NAME:
         print("❌ Error: LLM_BASE_URL o LLM_MODEL_NAME no encontrados en .env")
         sys.exit(1)
    
    print("=" * 80)
    print("🧪 PRUEBA DE GENERACIÓN DE IMÁGENES CON CONTEXTO (MODAL)")
    print("=" * 80)
    print("\nSelecciona el contexto para generar la imagen:")
    
    # Seleccionar ropa
    print_menu("👗 ROPA", CLOTHES_OPTIONS)
    clothes = get_user_choice(CLOTHES_OPTIONS, "Elige la ropa")
    
    # Seleccionar lugar
    print_menu("📍 LUGAR", LOCATION_OPTIONS)
    location = get_user_choice(LOCATION_OPTIONS, "Elige el lugar")
    
    # Seleccionar mood (opcional)
    print_menu("😊 ESTADO DE ÁNIMO (Opcional)", MOOD_OPTIONS)
    mood = get_user_choice(MOOD_OPTIONS, "Elige el estado de ánimo")

    # Seleccionar pose sexual
    print_menu("🔥 POSE SEXUAL", POSE_OPTIONS)
    sexual_pose = get_user_choice(POSE_OPTIONS, "Elige la pose sexual")
    
    # Crear contexto
    context = UserContext(
        user_id=999,  # ID de prueba
        clothes=clothes,
        location=location,
        mood=mood
    )
    
    # Seleccionar compañeros sexuales (puedes escoger múltiples separados por comas)
    print_menu("👥 COMPAÑEROS SEXUALES (elige varios separados por comas)", COMPANION_OPTIONS)
    companion_choices = input("Elige (ej: 1,3 para dildo + black_male): ").strip()
    selected_companions = []
    for choice in companion_choices.split(","):
        option = choice.strip()
        if option in COMPANION_OPTIONS:
            selected_companions.append(COMPANION_OPTIONS[option])
    companion_prompt = ", ".join(selected_companions)

    # Construir prompt
    image_prompt = build_image_prompt(context, sexual_pose, companion_prompt)
    
    print("\n" + "=" * 80)
    print("📋 RESUMEN DEL CONTEXTO:")
    print("=" * 80)
    print(f"  Ropa: {context.clothes}")
    print(f"  Lugar: {context.location}")
    print(f"  Mood: {context.mood}")
    print(f"  Pose sexual: {sexual_pose}")
    if companion_prompt:
        print(f"  Compañeros: {companion_prompt}")
    print(f"\n  Prompt generado (palabras clave): {image_prompt}")
    print("=" * 80)
    
    # Inicializar el agente para redactar el prompt
    print("\n📝 Inicializando agente de imagen (Grok) para redactar el prompt...")
    image_agent = ImagePromptAgent(api_key=LLM_API_KEY, model_name=LLM_MODEL_NAME, base_url=LLM_BASE_URL)
    print("✅ Agente inicializado")
    
    # Redactar el prompt con Grok
    print("\n✍️  Redactando prompt con Grok (convirtiendo palabras clave en frase narrativa)...")
    redacted_prompt = await image_agent.redact_image_prompt(image_prompt)
    print(f"✅ Prompt redactado: {redacted_prompt}")
    print("=" * 80)
    
    # Inicializar el generador (Modal — no API keys needed here)
    print("\n📦 Inicializando ImageGenerator (Modal)...")
    img_gen = ImageGenerator()
    print("✅ ImageGenerator inicializado")
    
    print("\n🎨 Generando imagen...")
    print("⏳ Esto puede tomar unos segundos...")
    print()
    
    try:
        # Generar imagen (async) con el prompt redactado — returns bytes
        image_bytes = await img_gen.generate_image(prompt=redacted_prompt)
        out_path = _save_image(image_bytes, prefix="test_ctx")
        
        print("=" * 80)
        print("✅ ¡Imagen generada exitosamente!")
        print("=" * 80)
        print()
        print(f"📁 Imagen guardada en: {out_path}")
        print()
        
        # Intentar abrir en el navegador (opcional)
        try:
            import webbrowser
            open_browser = input("¿Abrir imagen? (s/n): ").strip().lower()
            if open_browser == 's':
                print("🌐 Abriendo imagen...")
                webbrowser.open(str(out_path))
        except Exception as e:
            print(f"⚠️  No se pudo abrir automáticamente: {e}")

        # Opción de animar imagen (Wan 2.2 I2V) — animator still uses Replicate
        animate_choice = input("¿Animar imagen? (s/n): ").strip().lower()
        if animate_choice == 's':
            replicate_api_token = os.getenv("REPLICATE_API_TOKEN")
            if not replicate_api_token:
                print("❌ Error: REPLICATE_API_TOKEN no encontrada en .env (necesaria para animación)")
            else:
                import base64
                data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
                print("\n🎬 Animando imagen (puede tardar varios minutos)...")
                try:
                    animator = ImageAnimator(api_key=replicate_api_token)
                    video_url = await animator.animate_image(image=data_uri)
                    print("=" * 80)
                    print("✅ ¡Video generado!")
                    print("=" * 80)
                    print(f"🔗 URL del video:\n{video_url}\n")
                    open_video = input("¿Abrir video en el navegador? (s/n): ").strip().lower()
                    if open_video == 's':
                        import webbrowser
                        webbrowser.open(video_url)
                except Exception as e:
                    print(f"❌ Error animando imagen: {e}")
        
        return out_path
        
    except Exception as e:
        print("=" * 80)
        print("❌ Error generando imagen:")
        print("=" * 80)
        print(str(e))
        print()
        print("💡 Verifica:")
        print("  - Que tengas el token de Modal configurado (modal token set ...)")
        print("  - Que la app esté desplegada: modal deploy nova_anime_modal/app.py")
        print("  - Que tengas conexión a internet")
        
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_image_generation())
