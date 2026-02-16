"""Agente de generación de prompts de imagen con mapeo a tags reales de Danbooru.

Flujo:
  1. Recopila contexto completo (personaje, ubicación, mood, ropa, conversación).
  2. El LLM analiza la escena y genera un JSON estructurado con los conceptos visuales.
  3. Cada concepto se mapea a tags reales de Danbooru via fuzzy matching (rapidfuzz + SQLite).
  4. El LLM puede añadir tags extra que no existan en Danbooru (LoRA triggers, estilos, etc.).
  5. El prompt final se ensambla: quality tags → Danbooru tags → extras.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langsmith import traceable

from ..context import UserContext
from ..services.danbooru_db import DanbooruTagMapper

QUALITY_TAGS = (
    "masterpiece, best quality, amazing quality, very aesthetic, "
    "high resolution, ultra-detailed, absurdres, newest, scenery, detailed eyes"
)

STRUCTURED_PROMPT_TEMPLATE = """You are an expert at composing image generation prompts for anime-style models (ILXL/Stable Diffusion).

Your PRIMARY goal is to faithfully represent what is ACTUALLY HAPPENING in the conversation right now.
Use Danbooru tags from the database as your primary vocabulary. Write tags in Danbooru format (lowercase, underscores).

## STEP 1: THINK ABOUT THE SCENE (include this in the JSON as "reasoning")

Before writing ANY tags, answer these questions in your head:
- Where is the character RIGHT NOW? (not where the scene started, but where they ARE)
- What objects ACTUALLY EXIST in this location? A beach has sand, water, sky — NOT beds, sofas, or indoor furniture.
- What is the character physically doing? Describe it plainly.
- What would a PHOTO of this exact moment look like?

Write a 1-2 sentence description in the "reasoning" field. This helps you stay grounded before choosing tags.

## STEP 2: OUTPUT JSON

## JSON FIELDS:

### CONTEXT-DRIVEN (use asset data as REFERENCE, but adapt freely to match the scene):
- "background": Start from "Location details" below, but REWRITE completely if the situation demands it. The background must reflect WHERE the character actually is RIGHT NOW, not the initial location.
  Examples of adaptation:
    - Location is "beach" but they walked into the sea → ["ocean", "water up to waist", "waves", "shoreline in distance", "sunset sky"]
    - Location is "beach" but they went to a bar nearby → ["beach bar", "wooden counter", "tropical drinks", "string lights", "night"]
    - Location is "nightclub" but they stepped outside → ["city street at night", "neon signs", "nightclub entrance behind"]
  The asset location data is just a STARTING POINT. You have FULL FREEDOM to change every tag if the conversation context requires it.
- "subject": Always ["1girl"] for a single female character.
- "appearance": Physical traits from "Physical" below. IMPORTANT: only include traits that are VISIBLE from the camera angle. If the character is facing away, omit face details (eye color, expression). If she turns back around, re-include them. The full trait list is your MEMORY — use it to restore details when they become visible again.
- "clothing": Outfit tags from "Current clothes" as BASE. ADAPT freely: partially removed, soaked, disheveled, etc. If they're in water, add "wet clothes", "clinging fabric". If undressed, reflect exactly what remains.

### DYNAMIC (write freely — be faithful to what's happening):
- "pose": Body position and action. Be SPECIFIC and descriptive. Write full phrases, not single words.
  Examples: ["sitting on sand", "leaning back on hands"], ["doggy style", "sex from behind", "on all fours"], ["standing against wall", "arms crossed"]
  SEXUAL POSITIONS: Choose the CORRECT position based on what the user describes:
    - "kiss" / "beso" → "kiss, french kiss, lips, saliva"
    - "from behind" / "desde atrás" → "sex from behind, doggy style, on all fours"
    - "encima" / "on top" → "girl on top, cowgirl position, straddling"
    - "misionero" / "face to face" → "missionary, lying on back, legs spread"
    - "oral" → "fellatio, kneeling, pov"
  If physically interacting with the user, add "pov" and "1boy".
  NEVER use generic tags like "seductive pose" — describe the ACTUAL body position instead.
  SURFACE CONTACT: When the character is sitting or lying on a surface, specify WHERE the body makes contact clearly to avoid limbs clipping through the ground. Examples:
    - Sitting on sand → ["sitting on sand", "legs on sand", "feet on sand"] — legs rest ON TOP of the surface.
    - Sitting on bed → ["sitting on edge of bed", "feet on floor"] or ["sitting on bed", "legs folded on bed"]
    - Lying on sand → ["lying on sand", "on back", "legs on sand"]
  Always make it clear the body is ON the surface, not sinking into it.
- "expression": Facial expression (2-3 tags). ONLY if the face is visible from the camera angle. If facing away, use an EMPTY list [].
- "camera": Camera angle (1-2 tags). Choose the angle that best shows the action:
    - CASUAL SCENES (chatting, sitting, standing): Use EYE-LEVEL angles: "cowboy shot", "medium shot", "full body", "upper body". Do NOT use "from above" for casual scenes — it creates misleading compositions.
    - Sex from behind → "from behind" or "from below"
    - Girl on top → "from below" or "pov"
    - Missionary / face to face → "from above" or "pov"
    - Close-up moments → "close-up", "portrait"
  IMPORTANT: "from above" should ONLY be used when the viewer is physically above the character (e.g. missionary position, she's lying down). For a girl sitting on the ground in a casual scene, use "medium shot" or "cowboy shot" at eye level.
  Do NOT always default to "looking at viewer" — only use it when the character is actually facing the camera.
- "nsfw": Sexual/anatomical tags ONLY if the scene is explicit. Example: ["nude", "sex", "vaginal penetration"]. Empty list if SFW.

### EXTRAS (free-form, no restrictions):
- "extras": Quality enhancers, physics effects, weighted tags, descriptive phrases.
  Example: ["(detailed vulva:1.8)", "wet skin", "sweat dripping", "cinematic lighting"]
  You can also add a SHORT descriptive phrase about the scene if it helps: ["girl being taken from behind on the beach at sunset"]
  NEVER include generic vague tags like "seductive pose", "private beach at sunset" — be concrete.

### BANNED TAGS (NEVER use):
hand_on_hilt, sword, axe, weapon, blade, lance, shield, armor, helmet, king, knight, throne, castle, dragon, leaning forward, leaning_forward, leaning forward slightly

### ENVIRONMENTAL COHERENCE (CRITICAL):
Every object in the image MUST be physically possible in the current location. Ask yourself: "Does this object exist here?"
- BEACH: sand, water, waves, sky, palm trees, towel, surfboard — NO bed, sofa, pillow, carpet, desk, chair, bookshelf
- NIGHTCLUB: dance floor, lights, bar, speakers — NO bed, sand, trees, kitchen
- BEDROOM: bed, pillows, furniture — NO sand, waves, trees
- OCEAN/SEA: water, waves, horizon — NO sand nearby (it's far), no furniture
If a tag introduces an object that CANNOT physically be at the current location, DO NOT include it.

## CHARACTER INFO:
- Physical: {physical}
- Current clothes: {clothes}
- Available outfits: {outfits}

## SCENE:
- Location: {location}
- Location details: {location_details}
- Mood: {mood} — {mood_visuals}
- Initial action: {initial_action}
- Relationship: {relationship}

## CURRENT EXCHANGE:
User: "{user_message}"
Character: "{reply_text}"
{conversation_section}
{last_prompt_section}

## CRITICAL RULES:
1. The image MUST match what is ACTUALLY HAPPENING in the conversation RIGHT NOW. This is the most important rule. You have TOTAL FREEDOM to change ANY tag — background, clothing, pose, camera — if the conversation context demands it.
2. Physical interaction (touching, kissing, sex) → add "pov" and "1boy" to pose.
3. Vagina visible → add "(detailed vulva:1.8), (detailed pussy:1.8)" to extras.
4. Breasts visible → add "(detailed breasts:1.1)" to extras.
5. Appearance tags are CONDITIONAL on visibility: if the face is not visible (e.g. from behind), OMIT eye color and expression. Re-include them when the face is visible again.
6. Do NOT include quality tags (masterpiece, etc.) — added automatically.
7. You can add a SHORT descriptive phrase in extras to clarify the scene for the model.
8. COMPOSITION INTEGRITY: The combination of pose + camera MUST be coherent. Avoid compositions that suggest physical/sexual interaction when none is happening.
9. NEVER add generic tags like "seductive pose". Describe only the REAL physical position.
10. ENVIRONMENT ADAPTATION: Think about what the character would ACTUALLY SEE from their current position. If standing in the ocean, the sand is underfoot and the shore is behind — NOT in the background as if viewed from the beach. Rebuild the entire background from the character's perspective.
11. NEVER use the tag "leaning forward" or "leaning forward slightly". It causes the character to appear as if she is sitting on top of the viewer. Instead, use specific body positions like "sitting on sand, leaning back on hands", "standing straight", or "leaning against wall".
12. If the character is sitting on the ground, ALWAYS use "leaning back" or "sitting upright" to maintain a clear physical distance from the camera/viewer.
13. OBJECT REALITY CHECK: Before finalizing, review every tag and ask: "Does this object physically exist at {location}?" Remove anything that doesn't belong. A bed does NOT appear on a beach. A sofa does NOT appear in the ocean.

Output ONLY valid JSON (include "reasoning" field). No explanations, no markdown."""


class ImagePromptAgent:
    """Genera prompts de imagen ILXL mapeando conceptos a tags reales de Danbooru."""

    def __init__(self, api_key: str, model_name: str, base_url: str):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=0.5,
            base_url=base_url,
        )
        self.tag_mapper = DanbooruTagMapper()
        self.assets_path = Path(__file__).resolve().parent.parent.parent / "assets"
        self.world_types_json_path = self.assets_path / "world_types" / "world_types.json"
        self.moods_path = self.assets_path / "moods.json"
        self._locations_cache = None
        self._moods_cache = None

    def _load_locations(self) -> dict:
        if self._locations_cache is not None:
            return self._locations_cache
        locations_data = {}
        try:
            if self.world_types_json_path.exists():
                wt = json.loads(self.world_types_json_path.read_text(encoding="utf-8")).get("world_types", {})
                for wk, wi in wt.items():
                    folder = wi.get("folder", wk)
                    loc_file = self.assets_path / "world_types" / folder / "locations" / "locations.json"
                    if loc_file.exists():
                        locations_data[wk] = json.loads(loc_file.read_text(encoding="utf-8"))
            self._locations_cache = locations_data
        except Exception as e:
            logging.error(f"Error loading locations: {e}")
        return self._locations_cache or {}

    def _load_moods(self) -> dict:
        if self._moods_cache is not None:
            return self._moods_cache
        if not self.moods_path.exists():
            return {}
        try:
            data = json.loads(self.moods_path.read_text(encoding="utf-8"))
            self._moods_cache = data.get("moods", {})
        except Exception as e:
            logging.error(f"Error loading moods: {e}")
        return self._moods_cache or {}

    def _get_location_details(self, context: UserContext) -> str:
        """Obtiene los detalles de la ubicación actual (background + physics)."""
        current_loc = (context.location or "").lower()
        world_type = (context.world_type or "realistic").lower()

        if context.home and current_loc in context.home:
            d = context.home[current_loc]
            return f"{d.get('background_prompt', '')} | effects: {d.get('physics_effects', '')}"

        locs = self._load_locations().get(world_type, {})
        for loc_key, loc_data in locs.items():
            if loc_key in current_loc or current_loc in loc_key:
                return f"{loc_data.get('background_prompt', '')} | effects: {loc_data.get('physics_effects', '')}"
        return ""

    def _get_mood_visuals(self, mood: str) -> str:
        """Obtiene los tags visuales del mood actual."""
        moods = self._load_moods()
        m = moods.get(mood.lower(), {})
        return m.get("visual_tags", "")

    def _build_structured_prompt(
        self,
        context: UserContext,
        user_message: str,
        reply_text: str,
        conversation_history: Optional[list] = None,
        last_prompt: Optional[str] = None,
    ) -> str:
        """Construye el prompt para que el LLM genere el JSON estructurado."""
        outfits_text = ", ".join(f"{k}: {v}" for k, v in context.outfits.items()) if context.outfits else "none"

        conv_section = ""
        if conversation_history and len(conversation_history) > 0:
            recent = conversation_history[-4:]
            lines = []
            for msg in recent:
                role = "User" if hasattr(msg, "type") and msg.type == "human" else "Char"
                content = msg.content if hasattr(msg, "content") else str(msg)
                lines.append(f"  {role}: {content[:120]}")
            conv_section = "\n## RECENT CONVERSATION:\n" + "\n".join(lines)

        lp_section = ""
        if last_prompt:
            lp_section = f"\n## PREVIOUS PROMPT (maintain consistency, evolve from it):\n{last_prompt}"

        return STRUCTURED_PROMPT_TEMPLATE.format(
            physical=context.physical_description or "not specified",
            clothes=context.clothes or "not specified",
            outfits=outfits_text,
            location=context.location or "unknown",
            location_details=self._get_location_details(context),
            mood=context.mood or "neutral",
            mood_visuals=self._get_mood_visuals(context.mood or "neutral"),
            initial_action=context.initial_action or "none",
            relationship=context.relationship,
            user_message=user_message,
            reply_text=reply_text or "(no reply yet)",
            conversation_section=conv_section,
            last_prompt_section=lp_section,
        )

    def _parse_structured_json(self, raw: str) -> dict:
        """Parsea la respuesta del LLM como JSON, con limpieza de formato."""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
        logging.error(f"Failed to parse structured JSON: {text[:200]}")
        return {}

    def _assemble_prompt(self, structured: dict, context: UserContext) -> str:
        """Ensambla el prompt final mapeando conceptos a tags reales de Danbooru.

        Todos los campos pasan por el fuzzy mapper para asegurar que se usen tags
        estandarizados de Danbooru, manteniendo la coherencia con el modelo ILXL.
        """
        mapper_available = self.tag_mapper.available

        # Tags que NUNCA deben aparecer en el prompt (causan artefactos visuales no deseados)
        banned_tags = {
            "hand_on_hilt", "leaning"
        }

        # Log del razonamiento del agente si existe
        reasoning = structured.get("reasoning", "")
        if reasoning:
            logging.info(f"  🧠 Agent reasoning: {reasoning}")

        # Todos los campos se mapean contra Danbooru para estandarización
        all_fields = ["background", "subject", "appearance", "clothing",
                       "pose", "expression", "camera", "nsfw"]

        all_tags = []

        for field in all_fields:
            concepts = structured.get(field, [])
            if not concepts or not isinstance(concepts, list):
                continue
            for concept in concepts:
                if not concept:
                    continue
                
                norm = concept.lower().strip()
                norm_underscore = norm.replace(" ", "_")
                
                # Filtrar tags prohibidos antes del mapeo
                if norm_underscore in banned_tags or norm in banned_tags:
                    logging.debug(f"  BANNED tag removed: '{concept}'")
                    continue

                # Intentar mapear a Danbooru si el mapper está disponible
                if mapper_available:
                    mapped = self.tag_mapper.map_concept(norm)
                    if mapped:
                        if mapped not in all_tags:
                            all_tags.append(mapped)
                        continue

                # Si no hay mapeo o no está disponible, usar el original normalizado
                if norm_underscore not in all_tags:
                    all_tags.append(norm_underscore)

        # 3. Extras → passthrough directo (LoRA triggers, weighted tags, etc.)
        extras = structured.get("extras", [])
        extra_tags = []
        if isinstance(extras, list):
            for tag in extras:
                tag = tag.strip()
                if tag and tag not in all_tags and tag not in extra_tags:
                    extra_tags.append(tag)

        parts = [QUALITY_TAGS]
        if all_tags:
            parts.append(", ".join(all_tags))
        if extra_tags:
            parts.append(", ".join(extra_tags))

        return ", ".join(parts)

    @traceable(
        name="ImagePromptAgent",
        run_type="chain",
        tags=["image", "prompt", "danbooru"]
    )
    async def generate_image_prompt(
        self,
        context: UserContext,
        user_message: str,
        reply_text: Optional[str] = None,
        conversation_history: Optional[list] = None,
        last_prompt: Optional[str] = None,
    ) -> str:
        """Genera el prompt completo de imagen.

        Flujo:
          1. LLM → JSON estructurado con conceptos visuales
          2. Fuzzy matching → tags reales de Danbooru
          3. Ensamblado final → quality + danbooru + extras
        """
        logging.info(f"🎨 ImagePromptAgent | user={context.user_id} msg={context.msg_count}")

        prompt_text = self._build_structured_prompt(
            context, user_message, reply_text or "", conversation_history, last_prompt
        )

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt_text)])
            raw_output = (response.content or "").strip()
            structured = self._parse_structured_json(raw_output)

            if not structured:
                logging.warning("LLM did not return valid structured JSON, using fallback")
                return self._fallback_prompt(context)

            final_prompt = self._assemble_prompt(structured, context)

            mapped_count = len([t for f in ["background", "subject", "appearance", "clothing", "pose", "expression", "camera", "nsfw"] for t in structured.get(f, [])])
            extra_count = len(structured.get("extras", []))
            logging.info(f"  Structured: {mapped_count} concepts + {extra_count} extras")
            logging.info(f"✅ Final prompt: {final_prompt[:120]}...")
            return final_prompt

        except Exception as e:
            logging.error(f"❌ Error in ImagePromptAgent: {e}")
            return self._fallback_prompt(context)

    def _fallback_prompt(self, context: UserContext) -> str:
        """Prompt de fallback usando datos del contexto directamente."""
        parts = [QUALITY_TAGS, "1girl"]
        if context.physical_description:
            parts.append(context.physical_description)
        if context.clothes:
            parts.append(context.clothes)
        parts.append("standing, looking at viewer")

        mood_visuals = self._get_mood_visuals(context.mood or "neutral")
        if mood_visuals:
            parts.append(mood_visuals.split(",")[0].strip())

        loc_details = self._get_location_details(context)
        if loc_details:
            bg = loc_details.split("|")[0].strip()
            if bg:
                parts.insert(1, bg)

        return ", ".join(parts)
