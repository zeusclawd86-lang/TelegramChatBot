import asyncio
import logging
import os
import json
import time
import base64
import urllib.request
import urllib.error
from typing import Optional
import replicate


class ImageAnimator:
    """Service for animating images into videos using Replicate (Wan 2.2 Fast I2V)."""

    # Modelo de Replicate para imagen → video (Wan 2.2 Fast I2V)
    # La API de predicciones requiere el hash de versión completo (64 caracteres).
    ANIMATION_MODEL = "wan-video/wan-2.2-i2v-fast"
    ANIMATION_MODEL_VERSION = "b609b267d986d762a6d8679ac036d29e6d4454218df558db3aa4d0396ba55c59"

    def __init__(self, api_key: str):
        """
        Inicializa el animador de imágenes con la API key de Replicate.

        Args:
            api_key: API key de Replicate
        """
        self.api_key = api_key
        os.environ["REPLICATE_API_TOKEN"] = api_key
        self.replicate_client = replicate.Client(api_token=api_key)

    def _url_to_data_uri(self, url: str, max_bytes: int = 2 * 1024 * 1024) -> str:
        """Descarga una imagen desde URL y la devuelve como data URI (evita 429 cuando Replicate descarga desde Imgur)."""
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ReplicateBot/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip() or "image/png"
            if not content_type.startswith("image/"):
                content_type = "image/png"
            data = resp.read(max_bytes)
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{content_type};base64,{b64}"

    async def animate_image(
        self,
        image: str,
        prompt: Optional[str] = None,
        num_frames: int = 81,
        frames_per_second: int = 27,
        resolution: str = "480p",
        go_fast: bool = False,
        interpolate_output: bool = True,
        sample_shift: int = 12,
        lora_scale_transformer: float = 1.0,
        lora_scale_transformer_2: float = 1.0,
    ) -> str:
        """
        Anima una imagen usando Wan 2.2 Fast I2V (Replicate).
        
        Args:
            image: URL o data URI de la imagen a animar (obligatorio).
            prompt: Descripción del movimiento (ej: "breathing, subtle body movement, hair sway").
            num_frames: Número de frames del video (default: 81).
            frames_per_second: FPS del video (default: 27).
            resolution: "480p" o "720p" (default: "480p").
            go_fast: Si True, prioriza velocidad (default: False).
            interpolate_output: Interpolar salida para suavizar (default: True).
            sample_shift: Parámetro del modelo (default: 12).
            lora_scale_transformer: Escala LoRA transformer (default: 1.0).
            lora_scale_transformer_2: Escala LoRA transformer 2 (default: 1.0).
        
        Returns:
            URL del video generado.
        """
        default_prompt = (
            "breathing, subtle body movement, hair sway, seductive expression, "
            "smooth loop, detailed skin, bouncing breast"
        )
        # Asegurar URL string (Replicate puede devolver FileOutput desde generate_url en algunos flujos)
        image_url_str = image if isinstance(image, str) else (getattr(image, "url", None) or str(image))
        # Si la imagen es http(s), descargarla y enviar como data URI para evitar 429 de Imgur cuando Replicate la descargue
        if image_url_str.startswith(("http://", "https://")):
            loop = asyncio.get_event_loop()
            image_url_str = await loop.run_in_executor(None, lambda: self._url_to_data_uri(image_url_str))
        # Wan 2.2 Fast I2V: image, prompt, num_frames, frames_per_second, resolution, go_fast, interpolate_output, sample_shift, lora_scale_*
        input_params = {
            "image": image_url_str,
            "prompt": (prompt or default_prompt).strip(),
            "num_frames": num_frames,
            "frames_per_second": frames_per_second,
            "resolution": resolution,
            "go_fast": go_fast,
            "interpolate_output": interpolate_output,
            "sample_shift": sample_shift,
            "lora_scale_transformer": lora_scale_transformer,
            "lora_scale_transformer_2": lora_scale_transformer_2,
        }
        logging.info(f"⏳ Animando imagen con {self.ANIMATION_MODEL} (puede tardar varios minutos)...")
        try:
            # Usar API HTTP de Replicate para evitar FileOutput no serializable del cliente Python
            def _run_animate():
                token = self.api_key
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                body = json.dumps({"version": self.ANIMATION_MODEL_VERSION, "input": input_params}).encode()
                req = urllib.request.Request(
                    "https://api.replicate.com/v1/predictions",
                    data=body,
                    headers={**headers, "Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        pred = json.loads(resp.read().decode())
                except urllib.error.HTTPError as err:
                    detail = err.read().decode() if err.fp else ""
                    raise Exception(f"HTTP {err.code}: {detail.strip() or err.reason}")
                pred_id = pred["id"]
                urls_get = pred["urls"]["get"]
                # Esperar a que termine (poll cada 5s, máx ~10 min)
                for _ in range(120):
                    time.sleep(5)
                    req_get = urllib.request.Request(urls_get, headers=headers, method="GET")
                    with urllib.request.urlopen(req_get, timeout=30) as resp:
                        pred = json.loads(resp.read().decode())
                    status = pred.get("status")
                    if status == "succeeded":
                        out = pred.get("output")
                        if isinstance(out, list) and out:
                            return out[0] if isinstance(out[0], str) else getattr(out[0], "url", str(out[0]))
                        if isinstance(out, str):
                            return out
                        raise Exception(f"Output inesperado: {type(out)}")
                    if status in ("failed", "canceled"):
                        raise Exception(pred.get("error") or f"Predicción {status}")
                raise Exception("Timeout esperando el video")
            loop = asyncio.get_event_loop()
            video_url = await loop.run_in_executor(None, _run_animate)
            logging.info(f"✅ Video generado: {video_url}")
            return video_url
        except Exception as e:
            raise Exception(f"Error animando imagen: {str(e)}")
    
    async def disconnect(self):
        """Cierra la conexión (Replicate no requiere desconexión explícita)."""
        pass
