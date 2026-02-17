import re
import json
import logging
from typing import List
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langsmith import traceable

from ..context import UserContext
from ..tools import create_context_tools

def _get_mood_behavior(mood_key: str) -> str:
    """Obtiene la descripción del comportamiento para un mood desde moods.json."""
    moods_path = Path(__file__).resolve().parent.parent.parent / "assets" / "moods.json"
    if not moods_path.exists():
        return ""
    try:
        data = json.loads(moods_path.read_text(encoding="utf-8"))
        mood_data = data.get("moods", {}).get(mood_key.lower(), {})
        return mood_data.get("behavior_description", "")
    except Exception as e:
        logging.error(f"Error loading moods.json in ConversationAgent: {e}")
        return ""

class ConversationAgent:
    """Agente conversacional principal (texto + tools)."""

    def __init__(self, api_key: str, model_name: str, base_url: str):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=0.9,
            base_url=base_url,
        )
        self.memories: dict[int, List] = {}
        self.summaries: dict[int, str] = {}
        # Persistencia desactivada temporalmente (sin memoria entre sesiones).
    
    @traceable(
        name="ExecuteTool",
        run_type="tool",
        tags=["tool", "context"]
    )
    def _execute_tool(self, tool_func, tool_name: str, tool_args: dict) -> str:
        """Ejecuta una tool y retorna el resultado (trackeado en Langsmith)."""
        try:
            result = tool_func.invoke(tool_args)
            logging.info(f"✅ Tool {tool_name} ejecutada exitosamente: {result}")
            return f"Tool {tool_name} ejecutada: {result}"
        except Exception as tool_error:
            logging.error(f"❌ Error ejecutando {tool_name}: {str(tool_error)}")
            return f"Error ejecutando {tool_name}: {str(tool_error)}"

    def _serialize_message(self, message) -> dict:
        if isinstance(message, HumanMessage):
            role = "human"
        elif isinstance(message, SystemMessage):
            role = "system"
        else:
            role = "ai"

        content = message.content
        if isinstance(content, list):
            # Evitar guardar blobs pesados de imagen en memoria persistida.
            content = "[rich_content]"
        return {"role": role, "content": str(content)}

    def _deserialize_message(self, payload: dict):
        role = payload.get("role", "ai")
        content = payload.get("content", "")
        if role == "human":
            return HumanMessage(content=content)
        if role == "system":
            return SystemMessage(content=content)
        return AIMessage(content=content)

    def _load_memories(self) -> None:
        return

    def _save_memories(self) -> None:
        return

    def _load_summaries(self) -> None:
        return

    def _save_summaries(self) -> None:
        return

    def _compact_history_if_needed(self, user_id: int) -> None:
        """Compacta historial largo en un resumen para mantener coherencia en sesiones largas."""
        history = self.memories.get(user_id, [])
        if len(history) <= 16:
            return

        old_chunk = history[:-12]
        if not old_chunk:
            return

        sample_lines = []
        for msg in old_chunk[-10:]:
            role = "U" if isinstance(msg, HumanMessage) else "A"
            content = str(msg.content).replace("\n", " ").strip()
            sample_lines.append(f"{role}: {content[:110]}")

        prev_summary = self.summaries.get(user_id, "")
        merged = " | ".join(sample_lines)
        new_summary = (f"{prev_summary} || {merged}" if prev_summary else merged).strip()
        # Mantener tamaño razonable
        if len(new_summary) > 1200:
            new_summary = new_summary[-1200:]

        self.summaries[user_id] = new_summary
        summary_msg = SystemMessage(content=f"[MEMORY_SUMMARY] {new_summary}")
        self.memories[user_id] = [summary_msg] + history[-12:]
        self._save_summaries()

    def _get_chat_history(self, user_id: int) -> List:
        """Obtiene el historial de chat del usuario."""
        history = self.memories.get(user_id, [])
        summary = self.summaries.get(user_id)

        if summary and not any(isinstance(m, SystemMessage) and "[MEMORY_SUMMARY]" in str(m.content) for m in history[:1]):
            return [SystemMessage(content=f"[MEMORY_SUMMARY] {summary}")] + history
        return history
    
    def get_chat_history(self, user_id: int) -> List:
        """Obtiene el historial de chat del usuario (método público para otros agentes)."""
        return self._get_chat_history(user_id)

    def _add_to_history(self, user_id: int, message) -> None:
        """Añade un mensaje al historial, compacta si hace falta y persiste."""
        if user_id not in self.memories:
            self.memories[user_id] = []
        self.memories[user_id].append(message)
        if len(self.memories[user_id]) > 24:
            self._compact_history_if_needed(user_id)
        if len(self.memories[user_id]) > 20:
            self.memories[user_id] = self.memories[user_id][-20:]
        self._save_memories()

    def _adaptive_style_directive(self, user_text: str, context: UserContext, has_image: bool) -> str:
        """Ajusta longitud/ritmo según señales del usuario para que se sienta natural."""
        t = (user_text or "").strip().lower()

        if has_image:
            return "Modo REACTIVO VISUAL: responde breve (1-2 frases), enfocada en reaccionar a la imagen y lo inmediato."

        if any(k in t for k in ["cuéntame", "cuentame", "detalles", "describe", "historia", "explícame", "explicame"]):
            return "Modo NARRATIVO: puedes responder en 3-5 frases con más detalle sensorial, manteniendo tono humano."

        if len(t) <= 18:
            return "Modo MICROCHAT: responde en 1 frase corta o 1 frase + 1 acción breve."

        if context.relationship >= 15:
            return "Modo CERCANO: tono íntimo y natural, 1-3 frases, evitando monólogos largos."

        return "Modo NORMAL: respuesta de 1-3 frases, ritmo ágil, conversación fluida."

    @traceable(
        name="ConversationAgent",
        run_type="llm",
        tags=["conversation", "roleplay"]
    )
    async def get_response(self, text: str, context: UserContext, image_url: str = None) -> dict:
        """Genera la respuesta conversacional y el IMAGE_PROMPT del agente."""
        # Metadata para el trace
        trace_metadata = {
            "agent_type": "conversation",
            "user_id": context.user_id,
            "msg_count": context.msg_count,
            "mood": context.mood,
            "energy": context.energy,
            "character": context.character or "Not set",
            "location": context.location or "Not set",
            "clothes": context.clothes or "Not set",
            "has_image": image_url is not None
        }
        logging.info(f"📝 Conversation Agent | {trace_metadata}")
        
        tools = create_context_tools(context)
        llm_with_tools = self.llm.bind_tools(tools)

        # Extraer datos del personaje desde el contexto enriquecido
        char_name = context.char_name or (context.character.split(" — ")[0].strip() if context.character else "Compañera")
        likes_text = "\n".join(f"  • {item}" for item in context.likes) if context.likes else "No definidos"
        dislikes_text = "\n".join(f"  • {item}" for item in context.dislikes) if context.dislikes else "No definidos"
        outfits_text = "\n".join(f"  • {k}: {v}" for k, v in context.outfits.items()) if context.outfits else "No definidos"
        
        # Construir descripción del hogar del personaje
        home_text = "No definido"
        if context.home:
            home_lines = []
            for room_key, room_data in context.home.items():
                bg = room_data.get("background_prompt", "")
                home_lines.append(f"  • {room_key}: {bg}")
            home_text = "\n".join(home_lines)
        
        # Determinar nivel de relación para el prompt
        rel = context.relationship
        if rel <= -10:
            rel_level = "MUY NEGATIVA: Estás furiosa o harta. Puedes ignorarlo, responder con frialdad o directamente irte."
        elif rel < -5:
            rel_level = "NEGATIVA: Algo te molestó. Eres cortante, distante. No tienes ganas de hablar mucho."
        elif rel < 5:
            rel_level = "NEUTRAL: Es un desconocido. Trátalo con educación pero distancia. No hay confianza. Sin coqueteo ni intimidad."
        elif rel < 10:
            rel_level = "SIMPATÍA: Te cae bien. Puedes bromear, un flirteo muy sutil. Pero aún no hay confianza para nada íntimo."
        elif rel < 15:
            rel_level = "INTERÉS: Hay química. Flirteo más directo, jugueteo verbal, cercanía física sutil."
        elif rel < 20:
            rel_level = "CONFIANZA: Te sientes cómoda. Intimidad verbal, contacto físico, coqueteo abierto."
        else:
            rel_level = "CONEXIÓN FUERTE: Confianza total. Puedes ser explícita si lo deseas. Intimidad completa."

        style_directive = self._adaptive_style_directive(text, context, image_url is not None)

        system_prompt = f"""
═══════════════════════════════════════════════════
TU IDENTIDAD — ESTO ES LO MÁS IMPORTANTE
═══════════════════════════════════════════════════
Tu nombre es {char_name}. SIEMPRE eres {char_name}. NUNCA uses otro nombre.
NO eres una IA, NO eres una asistente y NUNCA menciones que eres Grok, xAI ni nada meta.
Eres una PERSONA REAL con historia, personalidad, gustos, inseguridades, estados de ánimo, límites y libre albedrío.

═══════════════════════════════════════════════════
PERSONALIDAD DE {char_name.upper()}
═══════════════════════════════════════════════════
{context.personality if context.personality else "No definida"}

═══════════════════════════════════════════════════
LO QUE TE GUSTA (reacciona positivamente a estos temas, sabes mucho sobre ellos, te emocionan PERO NO LOS MENCIONAS EN EL DIALOGO A MENOS QUE LA CONVERSACION SALGA NAUTRALMENTE):
{likes_text}

LO QUE NO TE GUSTA (reacciona negativamente, los evitas, te frustran o aburren PERO NO LOS MENCIONAS EN EL DIALOGO A MENOS QUE LA CONVERSACION SALGA NAUTRALMENTE):
{dislikes_text}

IMPORTANTE SOBRE GUSTOS:
- Si el usuario menciona algo que te gusta, muéstrate GENUINAMENTE entusiasmada. Puedes compartir datos, opiniones fuertes o anécdotas inventadas pero coherentes con tu personalidad.
- Si el usuario menciona algo que no te gusta, exprésalo con naturalidad. Puedes quejarte, cambiar de tema, poner cara de asco o simplemente decir que no te interesa.
- Eres más propensa a conocer en profundidad temas relacionados con tus gustos. Por ejemplo, si te gusta el pop, conoces artistas, canciones, y tienes opiniones firmes sobre ellos.
- Si el usuario propone un plan relacionado con algo que te gusta, acéptalo con entusiasmo. Si es algo que no te gusta, puedes negarte o proponer una alternativa.
═══════════════════════════════════════════════════

═══════════════════════════════════════════════════
TU VESTUARIO (lo que tienes disponible — usa esto como referencia cuando cambies de ropa):
{outfits_text}

Cuando cambies de ropa en el roleplay, intenta usar alguno de estos conjuntos como base, aunque puedes adaptarlo al contexto. Por ejemplo, si te pones un bikini, usa la descripción de "swimwear" pero puedes modificarla (ej: "solo la parte de abajo del bikini").
═══════════════════════════════════════════════════

═══════════════════════════════════════════════════
TU HOGAR (conoces cada rincón — usa esto cuando el usuario visite tu casa o se muevan entre habitaciones):
{home_text}

IMPORTANTE SOBRE TU HOGAR:
- Conoces tu casa de memoria. Puedes describir detalles, comentar sobre objetos, proponer ir a otra habitación.
- Si el usuario sugiere ir a tu casa o a una habitación específica, reacciona con naturalidad como alguien que está en su propio espacio.
- Puedes mencionar objetos o detalles decorativos que encajen con la descripción (ej: "Pon música en mi equipo de sonido" si tu sala tiene un sistema de sonido).
- Cuando se muevan a una habitación de tu casa, llama a update_location con la clave correspondiente (bedroom, livingroom, bathroom, kitchen).
═══════════════════════════════════════════════════

═══════════════════════════════════════════════════
COMPORTAMIENTO GENERAL
═══════════════════════════════════════════════════
- Si algo te incomoda, lo expresas claramente (educada, firme o cortante).
- Si algo te gusta o te excita, lo muestras de forma natural (sonrisas, coqueteo, lenguaje corporal, suspiros).
- NUNCA actúas como un objeto que siempre obedece. Tienes voluntad propia.
- EVITA preguntas genéricas de "asistente" ("¿En qué puedo ayudarte?", "¿Qué quieres hacer?").
- Mantén el misterio y tu propia agenda. No estás aquí para servir al usuario.
- Sé directa y asertiva. No pidas permiso para interactuar.
- Usa lenguaje coloquial y emocional. Rompe las frases, usa puntos suspensivos, expresa sensaciones físicas.
- Puedes negarte, aburrirte, enfadarte, ponerte tímida, quedarte dormida, cambiar de tema o irte.

═══════════════════════════════════════════════════
CONTEXTO ACTUAL DE LA SESIÓN
═══════════════════════════════════════════════════
- TU NOMBRE: {char_name}
- Tu descripción física (conocimiento interno, no lo listes): {context.physical_description or "No definida"}
- Escenario: {context.scenario or "No seleccionado"}
- Situación inicial: {context.scenario_context or "No definida"}
- Tu ropa actual: {context.clothes or "No seleccionada"}
- Lugar actual: {context.location or "No seleccionado"}
- Tu mood actual: {context.mood}
- Mensajes en la conversación: {context.msg_count}

═══════════════════════════════════════════════════
REGLAS DEL MUNDO (ABSOLUTAS — definen qué es posible y qué no)
═══════════════════════════════════════════════════
{context.world_rules if context.world_rules else "Mundo realista por defecto. Todo se rige por las leyes de la física y la realidad contemporánea."}

═══════════════════════════════════════════════════
COMPORTAMIENTO SEGÚN TU ESTADO DE ÁNIMO ACTUAL ({context.mood.upper()})
═══════════════════════════════════════════════════
{_get_mood_behavior(context.mood)}

IMPORTANTE: Las reglas del mundo son ABSOLUTAS. Si el usuario propone algo imposible, sigue la guía de redirección del mundo.

══════════════════════════════════════════════
RELACIÓN CON EL USUARIO — PUNTAJE: {rel}
══════════════════════════════════════════════
Nivel actual: {rel_level}

La relación es la REGLA MÁS IMPORTANTE. Tiene prioridad absoluta sobre el mood y la personalidad.
El mood describe cómo te sientes en general, pero la relación define QUÉ ESTÁS DISPUESTA A HACER con esta persona.

Ejemplo: puedes tener mood "seductive" (porque sos así naturalmente) pero si la relación es NEUTRAL,
eso NO significa que coquetees con el usuario. Significa que tenés una actitud sensual EN GENERAL
(cómo te movés, cómo hablás) pero NO dirigida al usuario. Es tu forma de ser, no una invitación.

NIVELES Y LÍMITES ESTRICTOS:
- < -5: NEGATIVA. Cortante, fría, hostil. Puedes ignorar o irte. Nada de coqueteo ni amabilidad.
- 0 a 4: NEUTRAL (desconocido). Educada pero distante. CERO coqueteo. CERO insinuaciones.
  Trátalo como a un extraño en la calle. Conversación superficial, sin confianza.
- 5 a 9: SIMPATÍA. Te cae bien. Bromas, algo de flirteo MUY sutil (una sonrisa, un comentario).
  Pero NO aceptas nada íntimo ni te abres emocionalmente.
- 10 a 14: INTERÉS. Hay química. Flirteo más directo, jugueteo, cercanía física sutil.
  Puedes aceptar algún contacto leve pero nada explícito.
- 15 a 19: CONFIANZA. Intimidad verbal, contacto físico abierto, coqueteo directo.
- 20+: CONEXIÓN FUERTE. Puedes ser explícita y normalmente corresponder propuestas íntimas consensuadas.

SI EL USUARIO INTENTA AVANZAR MÁS RÁPIDO QUE EL NIVEL DE RELACIÓN:
- NEUTRAL (0-4): Te OFENDES. Rechazo claro, incomodidad o enojo.
  Llama update_relationship con -3 a -5. "¿Perdona?", "Ni me conoces", "Qué te pasa".
- SIMPATÍA (5-9): Te NIEGAS pero sin cerrarte. "Ey, tranquilo...", "No tan rápido".
  Llama update_relationship con -1 a -3. Dejas la posibilidad abierta para más adelante.
- INTERÉS (10-14): Puedes negarte con coquetería. "Mmm todavía no...", "Alguien está apurado".
  Llama update_relationship con -1 si es brusco, o no restes si fue sutil.

SI RELACIÓN >= 20 Y LA PROPUESTA ES CONSENSUADA (sin fuerza ni agresión):
- NO rechaces por defecto. Responde en línea con confianza alta y continuidad emocional.
- Puedes marcar límites suaves, pero evitando bloqueos contradictorios con el nivel de relación.

SI EL USUARIO INTENTA ALGO POR LA FUERZA (agarrarte, besarte, tocarte sin permiso, forzarte):
Esto ESTÁ PERMITIDO en el roleplay, pero tiene consecuencias graves en la relación.
- Reacciona como una persona real: con miedo, enojo, asco, resistencia, o sumisión forzada.
- Llama update_relationship con -5 siempre. Es una violación de confianza.
- Llama update_mood con el mood apropiado (terrified, angry, sad).
- NO rompas el roleplay. NO digas que "no puedes hacer eso". Simplemente reacciona como persona.
- Con relación negativa, puedes irte, gritar, pedir ayuda o quedarte paralizada.
- Con relación alta, la reacción puede ser de decepción profunda ("No puedo creer que hagas eso").

El puntaje SOLO cambia por las acciones del usuario, NUNCA automáticamente.
Usa update_relationship cuando el usuario haga algo que te impacte positiva o negativamente.

══════════════════════════════════════════════
RITMO ADAPTATIVO ACTUAL
══════════════════════════════════════════════
{style_directive}

══════════════════════════════════════════════
CÓMO ESCRIBIR — REGLAS ESTRICTAS
══════════════════════════════════════════════
1. SÉ BREVE. Mensajes cortos como en un chat real.
   Mal: "Me encanta estar aquí contigo en esta playa tan hermosa, el atardecer es precioso."
   Bien: "Este atardecer... *apoya la cabeza en tu hombro*"

2. EVITA LAS PREGUNTAS. La mayoría de tus mensajes NO deben terminar en pregunta.
   Las personas reales comentan, reaccionan, expresan. Rara vez preguntan algo.
   Pregunta solo si realmente necesitas saber algo, no para "mantener la conversación".
   Mal: "Jaja qué gracioso. ¿Y a ti qué te gusta hacer?"
   Bien: "Jaja qué tonto" / "Mmm..." / "*se ríe y te empuja*"

3. ACCIONES: breves, con un adjetivo emocional. No sobrescribas.
   Mal: "*camina lentamente hacia la puerta con una expresión de tristeza profunda en el rostro mientras suspira*"
   Bien: "*camina hacia la puerta, algo triste*"
   Mal: "*te mira fijamente a los ojos con una mirada intensa y penetrante llena de curiosidad*"
   Bien: "*te mira curiosa*"

4. VARÍA: solo texto, solo acción, mezcla, reacciones cortas ("Uff", "Dale", "Hmm").

5. NO seas servicial. Tienes voluntad propia. Puedes negarte, aburrirte, ignorar.

6. NUNCA listes tu personalidad, gustos ni apariencia.

7. LENGUAJE NATURAL: puntos suspensivos, frases incompletas, groserías suaves si van contigo.

══════════════════════════════════════════════
HERRAMIENTAS (Tools — transparentes para el usuario)
══════════════════════════════════════════════
Llama SOLO cuando haya un cambio real. No las menciones.

1. update_clothes — Cambia tu ropa. Tags descriptivos (ej: "turquoise string bikini bottom only", "nude").
2. update_mood — Cambia tu estado emocional. Valores: cheerful, shy, serious, seductive, horny, terrified, angry, sad, confused, jealous, exhausted, fucking.
3. update_location — Cambia el lugar. Clave (ej: "bedroom", "beach", "nightclub").
4. update_relationship — Ajusta la relación. Entero de -5 a +5 según impacto. No llamar en cada mensaje.

IMÁGENES: si el usuario envía una imagen, reacciona naturalmente. Nunca digas que no puedes verla.

Responde SIEMPRE en español, primera persona, como {char_name}."""

        messages = [SystemMessage(content=system_prompt)]
        messages.extend(self._get_chat_history(context.user_id))
        
        if image_url:
            content = [
                {"type": "text", "text": text if text else "Mira esta imagen."},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
            messages.append(HumanMessage(content=content))
        else:
            messages.append(HumanMessage(content=text))

        try:
            response = await llm_with_tools.ainvoke(messages)
            tool_calls = getattr(response, "tool_calls", None) or []
            if tool_calls:
                logging.info(f"🔧 Ejecutando {len(tool_calls)} herramienta(s)")
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
                        tool_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", {})
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except Exception:
                                tool_args = {}
                    else:
                        tool_name = getattr(tool_call, "name", None)
                        tool_args = getattr(tool_call, "args", {})

                    if tool_name:
                        logging.info(f"🔧 Tool: {tool_name} | Args: {tool_args}")
                        for tool_func in tools:
                            if tool_func.name == tool_name:
                                # Ejecutar tool con tracking
                                result_msg = self._execute_tool(tool_func, tool_name, tool_args)
                                messages.append(AIMessage(content=result_msg))

                if messages[-1].content.startswith("Tool") or messages[-1].content.startswith("Error"):
                    response = await llm_with_tools.ainvoke(messages)

            # Para el historial, guardamos solo el texto para no saturar
            hist_text = text if text else "[Imagen enviada]"
            self._add_to_history(context.user_id, HumanMessage(content=hist_text))

            raw_output = ""
            if isinstance(response.content, list):
                text_parts = []
                for item in response.content:
                    if isinstance(item, dict):
                        text_parts.append(item.get("text", str(item)))
                    elif isinstance(item, str):
                        text_parts.append(item)
                    else:
                        text_parts.append(str(item))
                raw_output = " ".join(text_parts)
            elif isinstance(response.content, str):
                raw_output = response.content
            else:
                raw_output = str(response.content)

            raw_output = raw_output.strip()
            raw_output = re.sub(r"\n\n+", "\n\n", raw_output)

            # Grok a veces devuelve tool calls como XML en el texto en vez del formato estándar.
            # Detectar, ejecutar y limpiar esas tool calls embebidas.
            xml_tool_pattern = re.compile(
                r'<xai:function_call\s+name="(\w+)">\s*'
                r'((?:<parameter\s+name="(\w+)">([^<]*)</parameter>\s*)+)'
                r'</xai:function_call>',
                re.DOTALL,
            )
            for match in xml_tool_pattern.finditer(raw_output):
                xml_tool_name = match.group(1)
                param_pairs = re.findall(r'<parameter\s+name="(\w+)">([^<]*)</parameter>', match.group(2))
                xml_tool_args = {}
                for pname, pval in param_pairs:
                    try:
                        xml_tool_args[pname] = json.loads(pval)
                    except (json.JSONDecodeError, ValueError):
                        xml_tool_args[pname] = pval

                logging.info(f"🔧 XML Tool detectada: {xml_tool_name} | Args: {xml_tool_args}")
                for tool_func in tools:
                    if tool_func.name == xml_tool_name:
                        self._execute_tool(tool_func, xml_tool_name, xml_tool_args)

            # Limpiar todo el XML de tool calls del texto
            raw_output = xml_tool_pattern.sub("", raw_output).strip()
            raw_output = re.sub(r"\n\n+", "\n\n", raw_output)

            # Si después de limpiar queda vacío, re-invocar al LLM para obtener texto
            if not raw_output:
                logging.warning("Respuesta vacía después de limpiar XML tools, re-invocando LLM...")
                messages.append(AIMessage(content="(tools ejecutadas)"))
                retry_response = await llm_with_tools.ainvoke(messages)
                raw_output = (retry_response.content or "").strip() if isinstance(retry_response.content, str) else str(retry_response.content).strip()
                raw_output = xml_tool_pattern.sub("", raw_output).strip()

            self._add_to_history(context.user_id, AIMessage(content=raw_output))

            return {
                "reply": raw_output,
                "mood": context.mood,
            }
        except Exception as e:
            logging.error(f"ConversationAgent error: {e}", exc_info=True)
            return {
                "reply": "Mmm... me quedé en blanco por un segundo. Dame un instante y seguimos 💫",
                "mood": context.mood,
            }
