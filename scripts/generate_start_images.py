#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from core.services.image_gen import ImageGenerator
START_CONTENT_PATH = REPO_ROOT / "assets" / "characters.json"


def _load_start_content() -> dict[str, Any]:
    """Load the start content JSON file."""
    if not START_CONTENT_PATH.exists():
        raise FileNotFoundError(f"Start content JSON not found: {START_CONTENT_PATH}")
    return json.loads(START_CONTENT_PATH.read_text(encoding="utf-8"))


def _resolve_output_path(image_path: str) -> Path:
    """Resolve an image path to an absolute path inside the repo."""
    path = Path(image_path)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


async def _generate_images(
    overwrite: bool,
    batch_size: int,
    pause_seconds: int,
    min_interval_seconds: int,
    max_retries: int,
) -> None:
    """Generate all start images from the JSON configuration."""
    content = _load_start_content()
    image_gen = ImageGenerator()

    generated_in_batch = 0
    last_request_ts = 0.0
    for character_key, scenarios in content.items():
        if not isinstance(scenarios, dict):
            logging.warning(f"Invalid scenarios for {character_key}, skipping.")
            continue

        for scenario_id, entry in scenarios.items():
            if not isinstance(entry, dict):
                logging.warning(f"Invalid entry for {character_key}/{scenario_id}, skipping.")
                continue

            prompt = str(entry.get("prompt", "")).strip()
            image_path = str(entry.get("image_path", "")).strip()
            if not prompt or not image_path:
                logging.warning(f"Missing prompt/image_path for {character_key}/{scenario_id}, skipping.")
                continue

            output_path = _resolve_output_path(image_path)
            if output_path.exists() and not overwrite:
                logging.info(f"Skipping existing image: {output_path}")
                continue

            wait_needed = min_interval_seconds - (time.time() - last_request_ts)
            if wait_needed > 0:
                logging.info(f"Waiting {int(wait_needed)}s to respect rate limits...")
                await asyncio.sleep(wait_needed)

            logging.info(f"Generating {character_key}/{scenario_id} -> {output_path.name}")
            for attempt in range(1, max_retries + 1):
                try:
                    image_bytes = await image_gen.generate_image(prompt)
                    last_request_ts = time.time()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(image_bytes)
                    logging.info(f"Saved image to {output_path}")
                    break
                except Exception as exc:
                    error_text = str(exc)
                    is_rate_limit = "429" in error_text or "rate limit" in error_text.lower()
                    if attempt >= max_retries or not is_rate_limit:
                        raise
                    logging.warning(f"Rate limit hit. Retrying in {pause_seconds}s (attempt {attempt}/{max_retries})...")
                    await asyncio.sleep(pause_seconds)

            generated_in_batch += 1
            if generated_in_batch >= batch_size:
                logging.info(f"Batch limit reached. Waiting {pause_seconds} seconds...")
                await asyncio.sleep(pause_seconds)
                generated_in_batch = 0


def main() -> None:
    """CLI entrypoint for generating start images."""
    parser = argparse.ArgumentParser(description="Generate start images for characters/scenarios.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing images if they already exist.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="How many images to generate before waiting.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=int,
        default=60,
        help="Seconds to wait between batches.",
    )
    parser.add_argument(
        "--min-interval-seconds",
        type=int,
        default=12,
        help="Minimum seconds between individual requests.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries on rate limit errors.",
    )
    args = parser.parse_args()

    load_dotenv(dotenv_path=REPO_ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    asyncio.run(
        _generate_images(
            overwrite=args.overwrite,
            batch_size=args.batch_size,
            pause_seconds=args.pause_seconds,
            min_interval_seconds=args.min_interval_seconds,
            max_retries=args.max_retries,
        )
    )


if __name__ == "__main__":
    main()
