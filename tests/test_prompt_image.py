"""
Script de prueba para generar imágenes con prompts escritos manualmente.
Permite escribir el prompt directamente y generar la imagen sin pasar por el flujo completo.
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

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

from dotenv import load_dotenv
from core.services.image_gen import ImageGenerator
from core.services.animator import ImageAnimator

# Cargar variables de entorno
load_dotenv()


def _save_image(image_bytes: bytes, prefix: str = "test_prompt") -> Path:
    """Save image bytes to the outputs/ directory and return the path."""
    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{prefix}_{ts}.png"
    out_path.write_bytes(image_bytes)
    return out_path


async def test_manual_prompt():
    """Prueba la generación de una imagen con un prompt escrito manualmente."""
    
    print("=" * 80)
    print("🧪 PRUEBA DE GENERACIÓN DE IMÁGENES CON PROMPT MANUAL (MODAL)")
    print("=" * 80)
    print("\nEscribe el prompt que quieres usar para generar la imagen.")
    print("Puedes escribir:")
    print("  - Una frase narrativa (ej: 'A busty blonde woman wearing a swimsuit on the beach')")
    print("  - Palabras clave separadas por comas (ej: 'blonde, busty, swimsuit, beach')")
    print("  - Un prompt estructurado con clusters (ej: '{Environment: on beach, Clothes: swimsuit}')")
    print("\nPresiona Enter dos veces (línea vacía) para finalizar el prompt.")
    print("-" * 80)
    
    # Leer el prompt del usuario (múltiples líneas)
    prompt_lines = []
    empty_line_count = 0
    
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_line_count += 1
                if empty_line_count >= 1 and prompt_lines:
                    break
            else:
                empty_line_count = 0
                prompt_lines.append(line)
        except (EOFError, KeyboardInterrupt):
            if prompt_lines:
                break
            else:
                print("\n❌ Prompt vacío. Saliendo...")
                sys.exit(0)
    
    # Combinar todas las líneas en un solo prompt
    manual_prompt = "\n".join(prompt_lines).strip()
    
    if not manual_prompt:
        print("❌ Error: El prompt está vacío")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("📋 PROMPT (se usará tal cual; solo se aplica el negative prompt por defecto):")
    print("=" * 80)
    print(manual_prompt)
    print("=" * 80)
    
    # Inicializar el generador (Modal — no API keys needed)
    print("\n📦 Inicializando ImageGenerator (Modal)...")
    img_gen = ImageGenerator()
    print("✅ ImageGenerator inicializado")
    
    print("\n🎨 Generando imagen...")
    print("⏳ Esto puede tomar unos segundos...")
    print()
    
    try:
        # Generar imagen solo con el prompt del usuario; el negative prompt por defecto se aplica en image_gen
        image_bytes = await img_gen.generate_image(
            prompt=manual_prompt,
            prompt_only=True,
        )
        out_path = _save_image(image_bytes, prefix="test_manual")
        
        print("=" * 80)
        print("✅ ¡Imagen generada exitosamente!")
        print("=" * 80)
        print()
        print(f"📁 Imagen guardada en: {out_path}")
        print()

        # Opción de animar imagen (Wan 2.2 I2V); permite repetir con otro prompt
        animate_choice = input("¿Animar imagen? (s/n): ").strip().lower()
        while animate_choice == 's':
            replicate_api_token = os.getenv("REPLICATE_API_TOKEN")
            if not replicate_api_token:
                print("❌ Error: REPLICATE_API_TOKEN no encontrada en .env (necesaria para animación)")
                break
            print("\n📝 Prompt para el modelo de animación (describe el movimiento deseado).")
            print("   Ejemplo: breathing, subtle body movement, hair sway, seductive expression")
            print("   Deja vacío y Enter para usar el valor por defecto.")
            animation_prompt = input("Prompt de animación: ").strip() or None
            print("\n🎬 Animando imagen (puede tardar varios minutos)...")
            try:
                import base64
                data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
                animator = ImageAnimator(api_key=replicate_api_token)
                video_url = await animator.animate_image(image=data_uri, prompt=animation_prompt)
                print("=" * 80)
                print("✅ ¡Video generado!")
                print("=" * 80)
                print(f"🔗 URL del video:\n{video_url}\n")
            except Exception as e:
                print(f"❌ Error animando imagen: {e}")
            animate_choice = input("¿Animar de nuevo con otro prompt? (s/n): ").strip().lower()
        
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
        print("  - Que el prompt sea válido")
        
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_manual_prompt())
