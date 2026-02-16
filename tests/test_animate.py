"""
Script de prueba solo para animación (imagen → video).
Pide la URL de la imagen y el prompt de animación, luego llama al modelo Wan 2.2 A14B I2V.
"""

import os
import sys
import asyncio
import logging

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
from core.services.animator import ImageAnimator

# Cargar variables de entorno
load_dotenv()


async def test_animate():
    """Pide URL de imagen y prompt de animación, luego anima con Wan 2.2 A14B I2V."""
    replicate_api_token = os.getenv("REPLICATE_API_TOKEN")
    if not replicate_api_token:
        print("❌ Error: REPLICATE_API_TOKEN no encontrada en .env")
        sys.exit(1)

    print("=" * 80)
    print("🧪 PRUEBA DE ANIMACIÓN (Wan 2.2 Fast I2V)")
    print("=" * 80)
    print()
    print("URL de la imagen a animar:")
    print("  - Debe ser enlace DIRECTO a la imagen (ej: https://i.imgur.com/xxx.png), no una página (ej: imgur.com/a/xxx).")
    print("  - En Imgur: abre la imagen → clic derecho → «Copiar dirección de imagen».")
    image_url = input("URL imagen: ").strip()
    if not image_url:
        print("❌ URL vacía. Saliendo.")
        sys.exit(1)
    if not image_url.startswith(("http://", "https://")):
        print("❌ La URL debe comenzar con http:// o https://")
        sys.exit(1)

    print()
    print("Prompt de animación (describe el movimiento). Vacío = valor por defecto.")
    print("Ejemplo: breathing, subtle body movement, hair sway, seductive expression")
    animation_prompt = input("Prompt de animación: ").strip() or None

    print()
    print("📦 Inicializando ImageAnimator...")
    animator = ImageAnimator(api_key=replicate_api_token)
    print(f"   Modelo de animación: {animator.ANIMATION_MODEL}")
    print()

    animate_again = "s"
    while animate_again == "s":
        print("🎬 Animando imagen (puede tardar varios minutos)...")
        try:
            video_url = await animator.animate_image(image=image_url, prompt=animation_prompt)
            print("=" * 80)
            print("✅ ¡Video generado!")
            print("=" * 80)
            print(f"🔗 URL del video:\n{video_url}\n")
        except Exception as e:
            print(f"❌ Error animando imagen: {e}")

        animate_again = input("¿Animar de nuevo con otro prompt? (s/n): ").strip().lower()
        if animate_again == "s":
            animation_prompt = input("Nuevo prompt de animación: ").strip() or None

    await animator.disconnect()
    print("Listo.")


if __name__ == "__main__":
    asyncio.run(test_animate())
