import json
import logging
from pathlib import Path
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langsmith import traceable

from ..context import UserContext


class AnimationPromptAgent:
    """Agente especializado en generar prompts para animar imágenes estáticas.
    
    Recibe la imagen (como data-URI), el contexto completo del personaje y la conversación,
    y genera una prompt descriptiva del movimiento que debería tener la animación.
    
    El modelo Wan 2.2 I2V espera prompts en lenguaje natural describiendo el movimiento,
    no tags de Danbooru.
    """

    def __init__(self, api_key: str, model_name: str, base_url: str):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=0.6,
            base_url=base_url,
        )
        self.moods_path = Path(__file__).resolve().parent.parent.parent / "assets" / "moods.json"
        self._moods_cache = None

    def _load_moods(self) -> dict:
        """Carga las descripciones de moods desde moods.json."""
        if self._moods_cache is not None:
            return self._moods_cache
        if not self.moods_path.exists():
            return {}
        try:
            data = json.loads(self.moods_path.read_text(encoding="utf-8"))
            self._moods_cache = data.get("moods", {})
            return self._moods_cache
        except Exception as e:
            logging.error(f"Error loading moods.json in AnimationPromptAgent: {e}")
            return {}

    @traceable(
        name="AnimationPromptAgent",
        run_type="chain",
        tags=["animation", "prompt", "i2v"]
    )
    async def generate_animation_prompt(
        self,
        context: UserContext,
        image_data_uri: str,
        image_prompt: Optional[str] = None,
        conversation_history: Optional[list] = None,
    ) -> str:
        """Genera una prompt de animación basada en la imagen y el contexto.
        
        Args:
            context: Estado completo del usuario/personaje.
            image_data_uri: La imagen como data-URI (base64) para análisis visual.
            image_prompt: El prompt que se usó para generar la imagen (referencia).
            conversation_history: Historial reciente de la conversación.
            
        Returns:
            Prompt en lenguaje natural para el modelo de animación I2V.
        """
        logging.info(f"🎬 AnimationPromptAgent | user={context.user_id}")

        # Construir contexto de conversación reciente
        conversation_section = ""
        if conversation_history and len(conversation_history) > 0:
            recent = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
            conv_lines = []
            for msg in recent:
                role = "User" if hasattr(msg, 'type') and msg.type == "human" else "Character"
                content = msg.content if hasattr(msg, 'content') else str(msg)
                conv_lines.append(f"- {role}: {content[:150]}")
            conversation_section = "\n\n## RECENT CONVERSATION:\n" + "\n".join(conv_lines)

        # Obtener descripción del mood actual
        mood_desc = ""
        moods = self._load_moods()
        current_mood = (context.mood or "normal").lower()
        if current_mood in moods:
            mood_desc = moods[current_mood].get("behavior_description", "")

        # Referencia del prompt de imagen si existe
        image_prompt_section = ""
        if image_prompt:
            image_prompt_section = f"\n\n## IMAGE GENERATION PROMPT (reference for what the image contains):\n{image_prompt}"

        prompt_text = f"""You are an expert at writing animation prompts for image-to-video AI models (Wan 2.2 I2V).

You will receive a STATIC IMAGE and context about the character and scene. Your job is to describe
the MOVEMENT and ANIMATION that should happen, NOT what the image looks like.

## CHARACTER INFO:
- Name: {context.char_name or "Unknown"}
- Physical: {context.physical_description or "not provided"}
- Current clothes: {context.clothes or "not provided"}
- Current mood: {context.mood or "neutral"} — {mood_desc}
- Location: {context.location or "unknown"}{image_prompt_section}{conversation_section}

## ANIMATION RULES:
1. Describe MOVEMENT, not appearance. The model already sees the image.
2. Focus on natural body movements that match the mood and context:
   - Breathing, chest rising and falling
   - Hair movement (wind, turning head)
   - Subtle body sway, weight shifting
   - Facial micro-expressions (blinking, smiling, lip movements)
   - Hand/arm gestures if relevant
3. Keep movements SUBTLE and REALISTIC. Avoid drastic changes.
4. Match the mood: cheerful = energetic movements, seductive = slow and deliberate, sad = minimal movement.
5. If there's physical interaction in the conversation (kissing, touching), describe that movement.
6. Include environmental effects if relevant (wind, water, light flickering, etc.).
7. ALWAYS include "detailed skin, smooth animation" for quality.

## OUTPUT FORMAT:
Write a single line in English describing the animation. Keep it under 50 words.
Focus on: body movement, expression changes, hair/cloth physics, environmental effects.

## EXAMPLES:
- "breathing, subtle body movement, hair swaying in wind, warm smile widening, blinking, detailed skin, smooth animation"
- "slow hip sway, hand reaching forward, seductive lip bite, hair falling over shoulder, neon lights flickering, detailed skin, smooth animation"  
- "chest rising and falling, looking away shyly, fidgeting hands, slight blush deepening, detailed skin, smooth animation"
- "energetic dancing, hair bouncing, arms raised, laughing expression, colorful lights pulsing, detailed skin, smooth animation"

Generate the animation prompt now:"""

        try:
            # Construir mensaje multimodal con la imagen
            message_content = [
                {"type": "text", "text": prompt_text},
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_uri}
                },
            ]
            
            response = await self.llm.ainvoke([HumanMessage(content=message_content)])
            animation_prompt = (response.content or "").strip()

            # Limpieza
            for prefix in ("Animation:", "Prompt:", "Output:", "Result:"):
                if animation_prompt.lower().startswith(prefix.lower()):
                    animation_prompt = animation_prompt[len(prefix):].strip()

            if animation_prompt.startswith('"') and animation_prompt.endswith('"'):
                animation_prompt = animation_prompt[1:-1]
            elif animation_prompt.startswith("'") and animation_prompt.endswith("'"):
                animation_prompt = animation_prompt[1:-1]

            animation_prompt = animation_prompt.split("\n")[0].strip()

            # Asegurar tags de calidad de animación
            if "detailed skin" not in animation_prompt.lower():
                animation_prompt += ", detailed skin"
            if "smooth animation" not in animation_prompt.lower():
                animation_prompt += ", smooth animation"

            logging.info(f"✅ Animation prompt: {animation_prompt[:100]}...")
            return animation_prompt

        except Exception as e:
            logging.error(f"❌ Error generating animation prompt: {e}")
            # Fallback basado en el mood
            fallback_movements = {
                "cheerful": "breathing, energetic body movement, hair bouncing, bright smile, blinking, detailed skin, smooth animation",
                "seductive": "breathing, slow body sway, hair falling over shoulder, lips slightly parting, bedroom eyes, detailed skin, smooth animation",
                "horny": "heavy breathing, body trembling slightly, messy hair movement, panting, detailed skin, smooth animation",
                "shy": "breathing, fidgeting, looking away, slight blush, hands clasped, detailed skin, smooth animation",
                "sad": "slow breathing, minimal movement, downcast eyes blinking, hair slightly moving, detailed skin, smooth animation",
                "angry": "tense breathing, sharp head turn, furrowed brow, clenched jaw, detailed skin, smooth animation",
                "fucking": "intense rhythmic movement, heavy breathing, messy hair bouncing, ecstatic expression, detailed skin, smooth animation",
            }
            fallback = fallback_movements.get(
                current_mood,
                "breathing, subtle body movement, hair sway, blinking, detailed skin, smooth animation"
            )
            logging.info(f"⚠️ Fallback animation prompt: {fallback}")
            return fallback
