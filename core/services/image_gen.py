import asyncio
import logging
import re
import json
from typing import Optional

import modal

# Modal app / class names matching the deployed app
_MODAL_APP_NAME = "nova-anime-ilxl"
_MODAL_CLASS_NAME = "NovaAnimeModel"


class ImageGenerator:
    """Image generation service backed by a Modal-deployed Nova Anime ILXL model.

    The model is accessed via ``modal.Cls.from_name`` – no API keys required
    here; authentication is handled by the Modal token configured on the host.
    """

    def __init__(self):
        """Initialise the remote Modal model reference."""
        ModelCls = modal.Cls.from_name(_MODAL_APP_NAME, _MODAL_CLASS_NAME)
        self._model = ModelCls()

    # ------------------------------------------------------------------
    # Prompt-processing helpers (unchanged from the Replicate era)
    # ------------------------------------------------------------------

    def _has_cluster_format(self, prompt: str) -> bool:
        """True si el prompt tiene formato de clusters (Environment:, Clothes:, JSON, etc.)."""
        if not prompt:
            return False
        prompt_lower = prompt.lower().strip()
        cluster_indicators = [
            "environment:", "clothes:", "character:", "mood:",
            "situation:", "sexualcompanions:", "{", "}"
        ]
        return any(indicator in prompt_lower for indicator in cluster_indicators)

    def _is_tag_style_prompt(self, prompt: str) -> bool:
        """
        Detecta si el prompt es una línea de tags estilo Danbooru/ILXL (comma-separated keywords).
        Estos prompts no deben parsearse como clusters; se usan con prefijo/sufijo de calidad y POV.
        """
        if not prompt or self._has_cluster_format(prompt):
            return False
        stripped = prompt.strip()
        if "," not in stripped:
            return False
        narrative_indicators = [
            " a ", " an ", " the ", " is ", " are ", " was ", " were ",
            " wearing ", " getting ", " on ", " in ", " at ", " with ",
        ]
        prompt_lower = stripped.lower()
        if any(indicator in prompt_lower for indicator in narrative_indicators):
            return False
        return True

    def _is_redacted_prompt(self, prompt: str) -> bool:
        """
        Detecta si el prompt ya está redactado (es una frase narrativa) o viene en formato de clusters.
        """
        if not prompt:
            return False
        if self._has_cluster_format(prompt):
            return False
        prompt_lower = prompt.lower().strip()
        narrative_indicators = [
            " a ", " an ", " the ", " is ", " are ", " was ", " were ",
            " wearing ", " getting ", " sitting ", " standing ",
            " on ", " in ", " at ", " with ", " from ",
            " woman ", " man ", " girl ", " boy ",
        ]
        return any(indicator in prompt_lower for indicator in narrative_indicators)

    def _parse_agent_prompt(self, prompt: str) -> dict:
        """Parsea el prompt del agente que viene en formato JSON con clusters."""
        clusters = {}
        try:
            json_match = re.search(r'\{[^}]+\}', prompt, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                json_str = re.sub(r'\s+', ' ', json_str)
                parsed = json.loads(json_str)
                clusters = parsed
                logging.info("✅ Prompt del agente parseado como JSON estructurado")
                return clusters
        except Exception:
            pass

        cluster_patterns = {
            "Environment": r'Environment:\s*([^\n]+)',
            "Clothes": r'Clothes:\s*([^\n]+)',
            "Character": r'Character:\s*([^\n]+)',
            "Mood": r'Mood:\s*([^\n]+)',
            "Situation": r'Situation:\s*([^\n]+)',
            "SexualCompanions": r'SexualCompanions:\s*([^\n]+)'
        }
        for cluster_name, pattern in cluster_patterns.items():
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                clusters[cluster_name] = match.group(1).strip()

        if clusters:
            logging.info(f"✅ Clusters extraídos del prompt: {list(clusters.keys())}")
        else:
            logging.info("⚠️ No se encontraron clusters, usando prompt completo")
            clusters["Character"] = prompt.strip()
        return clusters

    def _build_structured_prompt(self, agent_prompt: str, pov_terms: str) -> str:
        """Construye un prompt estructurado con clusters organizados. Máximo 5 palabras clave por cluster."""
        agent_clusters = self._parse_agent_prompt(agent_prompt)
        quality_cluster = "masterpiece, best quality, amazing quality, 4k, very aesthetic"

        structured_prompt = "{\n"
        structured_prompt += f"Quality: {quality_cluster}\n"

        if "Environment" in agent_clusters:
            env_terms = agent_clusters['Environment'].split(", ")
            structured_prompt += f"Environment: {', '.join(env_terms[:5])}\n"
        else:
            structured_prompt += "Environment: in a room\n"

        if "Clothes" in agent_clusters:
            clothes_terms = agent_clusters['Clothes'].split(", ")
            structured_prompt += f"Clothes: {', '.join(clothes_terms[:5])}\n"
        else:
            structured_prompt += "Clothes: wearing clothes\n"

        if "SexualCompanions" in agent_clusters:
            companion_terms = agent_clusters['SexualCompanions'].split(", ")
            companion_simple = ", ".join([t.strip() for t in companion_terms if t][:5])
            if companion_simple:
                structured_prompt += f"SexualCompanions: {companion_simple}\n"
        else:
            structured_prompt += "SexualCompanions: solo\n"

        if "Situation" in agent_clusters:
            situation_terms = agent_clusters['Situation'].split(", ")
        elif "Character" in agent_clusters:
            situation_terms = agent_clusters['Character'].split(", ")
        else:
            situation_terms = ["neutral pose"]
        situation_clean = ", ".join([t.strip() for t in situation_terms if t][:5])
        structured_prompt += f"Situation: {situation_clean}\n"

        character_parts = []
        if "Character" in agent_clusters:
            char_terms = agent_clusters['Character'].split(", ")
            character_parts.extend([t.strip() for t in char_terms if t][:5])
        character_simple = ", ".join(character_parts[:5]) or "1girl"
        structured_prompt += f"Character: {character_simple}\n"

        if "Mood" in agent_clusters:
            mood_terms = agent_clusters['Mood'].split(", ")
            structured_prompt += f"Mood: {', '.join(mood_terms[:5])}\n"
        else:
            structured_prompt += "Mood: natural expression\n"

        pov_clean = pov_terms.replace(", ", "").replace(",", ", ") if pov_terms else "looking at viewer, eye contact"
        pov_terms_list = pov_clean.split(", ")
        structured_prompt += f"POV: {', '.join(pov_terms_list[:5])}\n"
        structured_prompt += "}"

        logging.info("✅ Prompt estructurado con clusters generado (máximo 5 términos por cluster)")
        return structured_prompt

    def _convert_structured_to_flat_prompt(self, structured_prompt: str) -> str:
        """Convierte un prompt estructurado con clusters a un prompt plano."""
        clusters = self._parse_agent_prompt(structured_prompt)
        prompt_parts = []

        prompt_parts.append(clusters.get("Quality", "masterpiece, best quality, amazing quality, 4k, very aesthetic"))
        if "Environment" in clusters:
            prompt_parts.append(clusters["Environment"])
        prompt_parts.append(clusters.get("Character", "1girl"))
        if "Clothes" in clusters:
            prompt_parts.append(clusters["Clothes"])
        if "Situation" in clusters:
            prompt_parts.append(clusters["Situation"])
        if "SexualCompanions" in clusters:
            prompt_parts.append(clusters["SexualCompanions"])
        if "Character" in clusters:
            prompt_parts.append(clusters["Character"])
        if "Mood" in clusters:
            prompt_parts.append(clusters["Mood"])
        if "POV" in clusters:
            prompt_parts.append(clusters["POV"])
        prompt_parts.append("anime art style, manga style, high quality anime illustration")

        return ", ".join(prompt_parts)

    # ------------------------------------------------------------------
    # Prompt assembly (builds final_prompt + negative from raw input)
    # ------------------------------------------------------------------

    def _build_final_prompt(
        self,
        prompt: str,
        style_prefix: Optional[str] = None,
        style_suffix: Optional[str] = None,
        prompt_only: bool = False,
    ) -> str:
        """Process the raw prompt into the final string sent to the model."""
        prompt_lower = prompt.lower()
        has_man = any(word in prompt_lower for word in ["man", "male", "guy", "boy", "men"])

        if has_man:
            pov_terms = "first person view, POV, from behind, looking away from viewer"
        else:
            pov_terms = "looking at viewer, eye contact, direct gaze, facing viewer, looking at camera"

        is_redacted = self._is_redacted_prompt(prompt)
        is_tag_style = self._is_tag_style_prompt(prompt)

        if prompt_only:
            final_prompt = prompt.strip()
            logging.info("✅ Usando prompt tal cual (prompt_only), sin agregados")
        elif style_prefix == "" and style_suffix == "":
            final_prompt = prompt.strip()
            logging.info("✅ Usando prompt sin agregados")
        elif style_prefix or style_suffix:
            default_prefix = style_prefix or "masterpiece, best quality, amazing quality, 4k, very aesthetic, high resolution, ultra-detailed, absurdres, newest, "
            default_suffix = style_suffix or f", {pov_terms}"
            final_prompt = f"{default_prefix}{prompt}{default_suffix}".strip()
        elif is_tag_style:
            quality_prefix = "masterpiece, best quality, amazing quality, 4k, very aesthetic, high resolution, ultra-detailed, absurdres, "
            anime_suffix = f", {pov_terms}, depth of field, volumetric lighting"
            final_prompt = f"{quality_prefix}{prompt}{anime_suffix}".strip()
            logging.info("✅ Prompt tags ILXL, agregando calidad y POV")
        elif is_redacted:
            anime_prefix = "masterpiece, best quality, amazing quality, 4k, very aesthetic, high resolution, ultra-detailed, absurdres, "
            anime_suffix = f", {pov_terms}, depth of field, volumetric lighting"
            final_prompt = f"{anime_prefix}{prompt}{anime_suffix}".strip()
            logging.info("✅ Prompt narrativo, agregando calidad y POV para ILXL")
        else:
            structured_prompt = self._build_structured_prompt(prompt, pov_terms)
            final_prompt = self._convert_structured_to_flat_prompt(structured_prompt)

        return final_prompt

    @staticmethod
    def _default_negative_prompt() -> str:
        """Return the standard negative prompt for Nova Anime ILXL."""
        return (
            "old, oldest, text, graphite, abstract, deformed, mutated, ugly, disfigured, long body, lowres, "
            "bad anatomy, bad hands, missing fingers, extra digit, fewer digits, very displeasing, "
            "(worst quality, bad quality:1.2), bad anatomy, sketch, jpeg artifacts, signature, watermark, "
            "username, simple background, conjoined, ai-generated, censored, censor, censor bars, "
            "body clipping, legs clipping through floor, buried legs, legs through ground, "
            "legs inside ground, sinking into ground, merged with floor, body merged with surface, "
            "loli, lolita, child, children, kid, kids, minor, underage, young girl, little girl, small girl, "
            "petite child, schoolgirl child, preteen, tween, toddler, baby, juvenile, childlike, "
            "childish appearance, underage appearance, looks underage, appears underage, "
            "looks like a child, appears like a child, looks like a minor, appears like a minor, "
            "young looking, youthful appearance, too young, very young, extremely young"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_image(
        self,
        prompt: str,
        style_prefix: Optional[str] = None,
        style_suffix: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        prompt_only: bool = False,
        num_inference_steps: int = 30,
        guidance_scale: float = 5.0,
        seed: Optional[int] = 86,
    ) -> bytes:
        """Generate a PNG image via the Modal-deployed Nova Anime ILXL model.

        Args:
            prompt: The raw prompt (tags, narrative, or cluster format).
            style_prefix: Custom text prepended to the prompt.
            style_suffix: Custom text appended to the prompt.
            negative_prompt: Custom negative prompt (default: built-in ILXL negative).
            prompt_only: If True, skip all automatic prefix/suffix processing.
            num_inference_steps: Inference steps (default 30).
            guidance_scale: CFG scale (default 5.0).
            seed: Seed for reproducibility (default: 86).

        Returns:
            Raw PNG image bytes.
        """
        try:
            final_prompt = self._build_final_prompt(
                prompt,
                style_prefix=style_prefix,
                style_suffix=style_suffix,
                prompt_only=prompt_only,
            )
            neg = negative_prompt or self._default_negative_prompt()

            logging.info(f"Prompt (primeros 100 chars): {final_prompt[:100]}...")
            logging.info(f"⏳ Generando imagen con Modal (Nova Anime ILXL) usando seed {seed}...")

            # Modal's .remote() is synchronous-blocking; run in executor to
            # keep the async event loop free.
            loop = asyncio.get_event_loop()
            image_bytes, timings = await loop.run_in_executor(
                None,
                lambda: self._model.predict_one.remote(
                    prompt=final_prompt,
                    prepend_preprompt=False,  # we already handle quality prefixes
                    negative_prompt=neg,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    seed=seed,
                ),
            )

            cold = timings.get("cold_start_seconds", 0)
            inf = timings.get("inference_seconds", 0)
            req_num = timings.get("request_number", "?")
            logging.info(
                f"✅ Imagen generada exitosamente "
                f"(cold={cold}s, inference={inf}s, request #{req_num})"
            )
            return image_bytes

        except Exception as e:
            raise Exception(f"Error en generación de imagen (Modal): {str(e)}")
