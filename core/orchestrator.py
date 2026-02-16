import logging
from typing import Optional, Union
from dataclasses import dataclass

from langsmith import traceable

from .context import ContextManager, UserContext
from .agents.conversation_agent import ConversationAgent
from .agents.image_prompt_agent import ImagePromptAgent
from .agents.animation_prompt_agent import AnimationPromptAgent
from .services.image_gen import ImageGenerator
from .services.animator import ImageAnimator


@dataclass
class OrchestratorResponse:
    text: str
    mood: Optional[str] = None
    no_energy: bool = False


# Costos de energía
ENERGY_COST_MESSAGE = 1
ENERGY_COST_IMAGE_TOTAL = 3  # Mensaje + Imagen = 3
ENERGY_COST_ANIMATION = 40


class ChatOrchestrator:
    """
    Orquestador agnóstico de plataforma (no sabe nada de Telegram).
    Maneja la lógica de negocio pura:
    1. Gestionar contexto de usuario
    2. Coordinar Agente LLM
    3. Exponer el prompt de imagen para que el adaptador decida cuándo generar
    """

    def __init__(
        self,
        llm_api_key: str,
        model_name: str,
        base_url: str,
        replicate_api_token: str,
    ):
        self.ctx_manager = ContextManager()
        self.chat_agent = ConversationAgent(api_key=llm_api_key, model_name=model_name, base_url=base_url)
        self.image_agent = ImagePromptAgent(api_key=llm_api_key, model_name=model_name, base_url=base_url)
        self.animation_agent = AnimationPromptAgent(api_key=llm_api_key, model_name=model_name, base_url=base_url)
        self.img_gen = ImageGenerator()
        self.animator = ImageAnimator(api_key=replicate_api_token)
        # Contador de imágenes por usuario (orquestador decide cuándo generar)
        self.image_counters: dict[int, int] = {}
        # Último prompt generado por usuario (para usar como ejemplo)
        self.last_prompts: dict[int, str] = {}
        # Cache para botón "Animar": key -> (data-URI, image_prompt) (callback_data tiene límite 64 bytes)
        self._animate_image_cache: dict[str, tuple[str, Optional[str]]] = {}

    def store_image_for_animate(self, key: str, image_data_uri: str, image_prompt: Optional[str] = None) -> None:
        """Guarda un data-URI de imagen y su prompt para poder animarla desde el callback del botón."""
        self._animate_image_cache[key] = (image_data_uri, image_prompt)

    def get_image_for_animate(self, key: str) -> Optional[tuple[str, Optional[str]]]:
        """Obtiene (data-URI, image_prompt) guardado para animar; None si no existe o ya se usó."""
        return self._animate_image_cache.pop(key, None)

    @traceable(
        name="Orchestrator_ProcessMessage",
        run_type="chain",
        metadata={"component": "orchestrator", "operation": "process_message"},
        tags=["orchestrator", "message"]
    )
    async def process_user_message(self, user_id: int, text: str, image_url: str = None) -> OrchestratorResponse:
        """Procesa un mensaje de usuario (texto y/u opcionalmente imagen) y devuelve la respuesta."""
        # 1. Obtener contexto
        ctx = self.ctx_manager.get_context(user_id)
        
        # Agregar metadata del contexto al trace
        logging.info(f"📊 Context: user_id={user_id}, msg_count={ctx.msg_count}, mood={ctx.mood}, energy={ctx.energy}")

        # 2. Validar energía mínima para un mensaje
        if not ctx.has_energy(ENERGY_COST_MESSAGE):
            return OrchestratorResponse(text="NO_ENERGY", no_energy=True)

        # 3. Validar estado del setup
        if not ctx.is_setup_complete:
            # Si es el primer mensaje y no ha hecho setup, devolvemos indicación especial
            if ctx.msg_count == 0:
                return OrchestratorResponse(text="SETUP_REQUIRED")

        # 4. Obtener respuesta del Agente con mecanismo de reintento
        max_retries = 3
        reply_text = ""
        
        for attempt in range(max_retries):
            try:
                agent_response = await self.chat_agent.get_response(text, ctx, image_url=image_url)
                reply_text = agent_response.get("reply", "").strip()
                
                # Validar que la respuesta no esté vacía
                if reply_text:
                    break
                else:
                    logging.warning(f"⚠️ Intento {attempt + 1}/{max_retries}: Respuesta vacía del agente para usuario {user_id}")
                    if attempt < max_retries - 1:
                        # Agregar un mensaje al contexto para que el agente entienda que debe responder
                        text = f"{text} (Por favor, responde con texto)"
            except Exception as e:
                logging.error(f"❌ Error en intento {attempt + 1}/{max_retries} del agente: {e}")
                if attempt == max_retries - 1:
                    # Último intento falló, usar fallback
                    reply_text = "Disculpa, estoy teniendo problemas para procesar tu mensaje. ¿Podrías intentar de nuevo?"
        
        # Si después de todos los reintentos aún está vacío, usar fallback
        if not reply_text:
            logging.error(f"❌ Agente no devolvió texto después de {max_retries} intentos para usuario {user_id}")
            reply_text = "Hmm... parece que me quedé sin palabras. ¿Podrías reformular tu mensaje?"

        # 5. Consumir energía base
        ctx.consume_energy(ENERGY_COST_MESSAGE)

        # Actualizar contadores
        ctx.msg_count += 1

        # La lógica de generación de imágenes se maneja en maybe_generate_image()
        return OrchestratorResponse(
            text=reply_text,
            mood=ctx.mood,
        )

    def get_user_context(self, user_id: int) -> UserContext:
        return self.ctx_manager.get_context(user_id)

    async def animate_image_with_energy(self, user_id: int, image_url: str, image_prompt: Optional[str] = None) -> str:
        """Anima una imagen si el usuario tiene suficiente energía.
        
        Usa el AnimationPromptAgent para generar una prompt de movimiento inteligente
        basada en la imagen, el contexto del personaje y la conversación.
        """
        ctx = self.ctx_manager.get_context(user_id)
        if not ctx.has_energy(ENERGY_COST_ANIMATION):
            raise Exception("NO_ENERGY")

        # Generar prompt de animación con el agente especializado
        conversation_history = self.chat_agent.get_chat_history(user_id)
        try:
            animation_prompt = await self.animation_agent.generate_animation_prompt(
                context=ctx,
                image_data_uri=image_url,
                image_prompt=image_prompt,
                conversation_history=conversation_history,
            )
            logging.info(f"🎬 Animation prompt generado: {animation_prompt[:100]}...")
        except Exception as e:
            logging.error(f"⚠️ Error en AnimationPromptAgent, usando fallback: {e}")
            animation_prompt = "breathing, subtle body movement, hair sway, blinking, detailed skin, smooth animation"

        video_url = await self.animator.animate_image(image=image_url, prompt=animation_prompt)
        ctx.consume_energy(ENERGY_COST_ANIMATION)
        return video_url

    @traceable(
        name="Orchestrator_GenerateImage",
        run_type="chain",
        metadata={"component": "orchestrator", "operation": "generate_image"},
        tags=["orchestrator", "image"]
    )
    async def maybe_generate_image(
        self,
        user_id: int,
        user_message: str,
        reply_text: str,
    ) -> Optional[bytes]:
        """
        Genera imagen cuando corresponde (primer mensaje o cada 3 mensajes).
        Usa el ImagePromptAgent para crear tags ILXL optimizados basándose en el contexto completo.

        Args:
            user_id: ID del usuario
            user_message: Mensaje del usuario
            reply_text: Respuesta del agente de conversación

        Returns:
            PNG image bytes, or None if no image was generated.
        """
        ctx = self.ctx_manager.get_context(user_id)
        
        # Agregar metadata del contexto al trace
        logging.info(f"🖼️ Image generation: user_id={user_id}, counter={self.image_counters.get(user_id, 0) + 1}")
        current_count = self.image_counters.get(user_id, 0) + 1
        self.image_counters[user_id] = current_count

        should_generate = current_count == 1 or current_count % 3 == 0
        if not should_generate:
            return None

        # Verificar si tiene energía suficiente para la imagen (ENERGY_COST_IMAGE_TOTAL - ENERGY_COST_MESSAGE = 2 adicionales)
        additional_cost = ENERGY_COST_IMAGE_TOTAL - ENERGY_COST_MESSAGE
        if not ctx.has_energy(additional_cost):
            logging.warning(f"⚠️ Usuario {user_id} no tiene energía suficiente para generar imagen.")
            return None

        # Validar que tenemos los datos necesarios
        if not user_message or not reply_text:
            logging.warning(f"⚠️ No se puede generar imagen sin mensaje de usuario y respuesta")
            return None

        # Obtener historial de conversación y último prompt para contexto
        conversation_history = self.chat_agent.get_chat_history(user_id)
        last_prompt = self.last_prompts.get(user_id)

        # Generar prompt usando el agente (único método)
        try:
            prompt_for_image = await self.image_agent.generate_image_prompt(
                ctx, 
                user_message, 
                reply_text,
                conversation_history=conversation_history,
                last_prompt=last_prompt
            )
        except Exception as e:
            logging.error(f"❌ Error generando prompt: {e}")
            return None

        if not prompt_for_image:
            logging.warning(f"⚠️ El agente no generó un prompt válido")
            return None

        try:
            image_bytes = await self.img_gen.generate_image(prompt_for_image)
            # Guardar este prompt como el último para futuras referencias
            self.last_prompts[user_id] = prompt_for_image
            # Consumir la energía adicional ahora que sabemos que se generó
            ctx.consume_energy(additional_cost)
            logging.info(f"🖼️ Imagen generada para usuario {user_id} (contador: {current_count})")
            logging.info(f"📝 Prompt guardado: {prompt_for_image[:80]}...")
            return image_bytes
        except Exception as e:
            logging.error(f"Error generando imagen para usuario {user_id}: {e}")
            return None
