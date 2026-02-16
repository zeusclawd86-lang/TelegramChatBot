import asyncio
import base64
import logging
import os
import urllib.request
from pathlib import Path
from typing import Optional, Union

import modal


class ImageAnimator:
    """Service for animating images using the AnimationModal app on Modal."""

    def __init__(self, api_key: Optional[str] = None):
        # api_key is kept for backward compatibility with existing orchestrator wiring.
        # Animation now uses Modal auth configured on the host (`modal setup`).
        self.api_key = api_key

        app_name = os.getenv("ANIMATION_MODAL_APP_NAME", "dasiwa-animate")
        class_name = os.getenv("ANIMATION_MODAL_CLASS_NAME", "ModalDaSiWaAnimator")

        AnimatorCls = modal.Cls.from_name(app_name, class_name)
        self._animator = AnimatorCls()

    def _to_image_bytes(self, image: str) -> bytes:
        """Convert image input (data URI, URL or local path) to bytes."""
        if not isinstance(image, str) or not image.strip():
            raise ValueError("Image input is empty")

        image = image.strip()

        # data:image/<type>;base64,<payload>
        if image.startswith("data:image"):
            try:
                encoded = image.split(",", 1)[1]
                return base64.b64decode(encoded)
            except Exception as e:
                raise ValueError(f"Invalid image data URI: {e}")

        # http(s) URL
        if image.startswith(("http://", "https://")):
            req = urllib.request.Request(
                image,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AnimationModalClient/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()

        # local path fallback
        path = Path(image)
        if path.exists() and path.is_file():
            return path.read_bytes()

        raise ValueError("Unsupported image format. Use data URI, URL, or local file path.")

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
    ) -> Union[bytes, str]:
        """
        Animate an image using AnimationModal.

        Returns bytes (mp4) when the remote class returns binary content.
        """
        default_prompt = "breathing, subtle body movement, hair sway, blinking, smooth motion"
        final_prompt = (prompt or default_prompt).strip()

        image_bytes = self._to_image_bytes(image)

        # Map old Wan/Replicate-oriented params to AnimationModal params as best-effort.
        seconds = max(1.0, min(8.0, num_frames / max(frames_per_second, 1)))
        params = {
            "prompt": final_prompt,
            "seconds": seconds,
            "fps": frames_per_second,
            "steps": 8 if go_fast else 10,
            "cfg": 1.8,
            "shift": float(sample_shift),
            "perfect_loop": bool(interpolate_output),
        }

        logging.info("⏳ Animating with AnimationModal app on Modal...")

        def _run_remote():
            return self._animator.animate.remote(
                image_data=image_bytes,
                params=params,
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_remote)

        if not result:
            raise Exception("AnimationModal returned empty result")

        if isinstance(result, (bytes, bytearray)):
            logging.info("✅ Animation generated (bytes)")
            return bytes(result)

        # In case future implementations return URL/string
        logging.info("✅ Animation generated (non-bytes)")
        return str(result)

    async def disconnect(self):
        """No explicit disconnect required for Modal client."""
        pass
