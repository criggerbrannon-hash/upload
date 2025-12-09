"""
Prompts Generator Module
========================

This module generates image and video prompts from SRT files using Google's Gemini API.
It analyzes the story content and creates consistent character descriptions and scene prompts.

Usage:
    generator = PromptGenerator(settings)
    generator.generate_for_project(project_dir, overwrite=False)
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from .utils import (
    Settings,
    get_logger,
    parse_srt,
    group_srt_into_scenes
)
from .excel_manager import PromptWorkbook, Character, Scene


# ============================================================================
# Gemini API Configuration
# ============================================================================

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Prompt templates for Gemini
SYSTEM_PROMPT_CHARACTERS = """
You are a creative director for video production. Analyze the following story script
and identify the main characters. For each character:

1. Identify the MAIN CHARACTER (nhân vật chính - abbreviated as "nvc")
2. Identify SUPPORTING CHARACTERS (nhân vật phụ - abbreviated as "nvp1", "nvp2", etc.)

For each character, create a detailed visual description in English that can be used
for AI image generation. The description should include:
- Age and gender
- Physical appearance (face shape, hair color/style, eye color, skin tone)
- Typical clothing/outfit style
- Overall vibe/personality that shows through appearance
- Any distinctive features

Make the characters visually appealing, emotionally engaging, and suitable for storytelling.

Return the result as a JSON object with this structure:
{
    "characters": [
        {
            "id": "nvc",
            "role": "main",
            "name": "Character name from story",
            "english_prompt": "Detailed visual description in English...",
            "vietnamese_prompt": "Brief description in Vietnamese (optional)"
        },
        {
            "id": "nvp1",
            "role": "supporting",
            "name": "Supporting character name",
            "english_prompt": "Detailed visual description...",
            "vietnamese_prompt": ""
        }
    ]
}

IMPORTANT: Only return valid JSON, no additional text or explanation.
"""

SYSTEM_PROMPT_SCENES = """
You are a creative director for video production. Based on the character descriptions
and the scene content, create detailed prompts for:

1. IMAGE PROMPT: A detailed description for AI image generation that depicts the scene.
   - Describe the setting, lighting, mood, and composition
   - ALWAYS include character consistency instructions like:
     "The main character must look exactly like nvc.png: same face, age, hair color and style."
     "Supporting character should match nvp1.png exactly."
   - Include emotional tone and atmosphere
   - Specify camera angle/shot type (close-up, wide shot, etc.)

2. VIDEO PROMPT: A description for video generation from the image.
   - Describe camera movement (pan, zoom, static, etc.)
   - Describe character movements and actions
   - Describe any environmental motion (wind, water, etc.)
   - Include mood/pacing
   - ALWAYS reference character consistency

Return the result as a JSON object:
{
    "scenes": [
        {
            "scene_id": 1,
            "img_prompt": "Detailed image generation prompt...",
            "video_prompt": "Video generation prompt with movements..."
        }
    ]
}

IMPORTANT: Only return valid JSON, no additional text.
"""


# ============================================================================
# PromptGenerator Class
# ============================================================================

class PromptGenerator:
    """
    Generates prompts for image and video generation using Gemini API.

    Supports multiple API keys and models with automatic rotation on rate limit.

    Attributes:
        settings: Application settings.
        logger: Logger instance.
        api_keys: List of Gemini API keys.
        models: List of Gemini models.
        current_key_index: Index of current API key being used.
        current_model_index: Index of current model being used.
    """

    def __init__(
        self,
        settings: Settings,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the PromptGenerator.

        Args:
            settings: Application settings containing API configuration.
            logger: Optional logger instance.
        """
        self.settings = settings
        self.logger = logger or get_logger("ve3_tool.prompts_generator")

        # Hỗ trợ nhiều API keys và models
        self.api_keys = settings.gemini_api_keys
        self.models = settings.gemini_models
        self.current_key_index = 0
        self.current_model_index = 0

        if not self.api_keys or self.api_keys[0] == "YOUR_GEMINI_API_KEY_HERE":
            raise ValueError(
                "Gemini API key not configured.\n"
                "Please set your API key in config/settings.yaml\n"
                "Get a free API key at: https://makersuite.google.com/app/apikey"
            )

        self.logger.info(f"Loaded {len(self.api_keys)} API keys, {len(self.models)} models")

    @property
    def api_key(self) -> str:
        """Get current API key."""
        return self.api_keys[self.current_key_index]

    @property
    def model(self) -> str:
        """Get current model."""
        return self.models[self.current_model_index]

    def _rotate_api_key(self) -> bool:
        """
        Rotate to the next API key.

        Returns:
            True if rotated successfully, False if all keys exhausted.
        """
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        if self.current_key_index == 0:
            # Đã xoay hết vòng, thử model tiếp theo
            return self._rotate_model()
        self.logger.info(f"Rotated to API key #{self.current_key_index + 1}")
        return True

    def _rotate_model(self) -> bool:
        """
        Rotate to the next model.

        Returns:
            True if rotated successfully, False if all models exhausted.
        """
        self.current_model_index = (self.current_model_index + 1) % len(self.models)
        self.logger.info(f"Rotated to model: {self.model}")
        return True

    def generate_for_project(
        self,
        project_dir: Path,
        overwrite: bool = False
    ) -> PromptWorkbook:
        """
        Generate prompts for a project from its SRT file.

        Args:
            project_dir: Path to the project directory.
            overwrite: If True, regenerate prompts even if they exist.

        Returns:
            PromptWorkbook with generated prompts.

        Raises:
            FileNotFoundError: If SRT file doesn't exist.
            RuntimeError: If Gemini API call fails.
        """
        project_dir = Path(project_dir)
        code = project_dir.name

        self.logger.info(f"Generating prompts for project: {code}")

        # Find SRT file
        srt_path = project_dir / "srt" / f"{code}.srt"
        if not srt_path.exists():
            raise FileNotFoundError(
                f"SRT file not found: {srt_path}\n"
                f"Please run voice_to_srt first."
            )

        # Load or create Excel workbook
        excel_path = project_dir / "prompts" / f"{code}_prompts.xlsx"
        workbook = PromptWorkbook(self.logger)
        workbook.load_or_create(excel_path)

        # Check if prompts already exist
        if workbook.has_prompts() and not overwrite:
            self.logger.info("Prompts already exist. Use --overwrite-prompts to regenerate.")
            return workbook

        # Parse SRT file
        self.logger.info("Parsing SRT file...")
        srt_entries = parse_srt(srt_path)

        if not srt_entries:
            raise ValueError(f"No valid entries found in SRT file: {srt_path}")

        # Group into scenes
        self.logger.info("Grouping into scenes...")
        scenes = group_srt_into_scenes(
            srt_entries,
            min_duration=self.settings.min_scene_duration,
            max_duration=self.settings.max_scene_duration
        )

        self.logger.info(f"Created {len(scenes)} scenes from {len(srt_entries)} subtitles")

        # Get full story text for character analysis
        full_story = self._get_full_story_text(srt_entries)

        # Step 1: Generate character descriptions
        self.logger.info("Analyzing characters with Gemini...")
        characters = self._generate_characters(full_story)

        # Clear existing data if overwriting
        if overwrite:
            workbook.clear_characters()
            workbook.clear_scenes()

        # Add characters to workbook
        for char in characters:
            workbook.add_character(char)

        workbook.save()
        self.logger.info(f"Added {len(characters)} characters")

        # Step 2: Generate scene prompts
        self.logger.info("Generating scene prompts with Gemini...")
        scene_prompts = self._generate_scene_prompts(scenes, characters)

        # Add scenes to workbook
        for scene_data in scenes:
            scene_id = scene_data['scene_id']
            prompts = scene_prompts.get(scene_id, {})

            scene = Scene(
                scene_id=scene_id,
                srt_start=scene_data['start_time'],
                srt_end=scene_data['end_time'],
                srt_text=scene_data['text'][:500],  # Limit text length
                img_prompt=prompts.get('img_prompt', ''),
                video_prompt=prompts.get('video_prompt', ''),
                img_path='',
                video_path='',
                status_img='pending',
                status_vid='pending'
            )
            workbook.add_scene(scene)

        workbook.save()
        self.logger.info(f"Added {len(scenes)} scenes with prompts")

        return workbook

    def _get_full_story_text(self, entries: list) -> str:
        """Combine all SRT entries into full story text."""
        return ' '.join(entry.text for entry in entries)

    def _call_gemini(self, prompt: str, system_prompt: str = "") -> str:
        """
        Call Gemini API with the given prompt.

        Supports automatic API key and model rotation on rate limit or errors.

        Args:
            prompt: User prompt.
            system_prompt: System instructions.

        Returns:
            Gemini response text.

        Raises:
            RuntimeError: If API call fails after all retries and rotations.
        """
        # Build request body
        contents = []

        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "I understand. I will follow these instructions."}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 8192,
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        # Make request with retry and rotation
        max_retries = self.settings.max_retries
        retry_delay = self.settings.retry_delay
        total_keys = len(self.api_keys)
        total_models = len(self.models)
        max_total_attempts = max_retries * total_keys * total_models

        for attempt in range(max_total_attempts):
            url = GEMINI_API_URL.format(model=self.model)
            url = f"{url}?key={self.api_key}"

            try:
                self.logger.debug(f"Calling Gemini API (key #{self.current_key_index + 1}, model: {self.model})")
                response = requests.post(url, headers=headers, json=body, timeout=120)

                if response.status_code == 200:
                    result = response.json()
                    candidates = result.get('candidates', [])
                    if candidates:
                        content = candidates[0].get('content', {})
                        parts = content.get('parts', [])
                        if parts:
                            return parts[0].get('text', '')

                    raise RuntimeError("Empty response from Gemini API")

                elif response.status_code == 429:
                    # Rate limited - rotate to next key
                    self.logger.warning(f"Rate limited on key #{self.current_key_index + 1}, rotating...")
                    self._rotate_api_key()
                    time.sleep(retry_delay)
                    continue

                elif response.status_code in [400, 403]:
                    # Bad request or forbidden - try next key/model
                    error_msg = response.text
                    self.logger.warning(f"API error {response.status_code}: {error_msg[:100]}")
                    self._rotate_api_key()
                    time.sleep(1)
                    continue

                else:
                    error_msg = response.text
                    self.logger.error(f"Gemini API error: {response.status_code} - {error_msg}")
                    self._rotate_api_key()
                    time.sleep(retry_delay)
                    continue

            except requests.exceptions.Timeout:
                self.logger.warning(f"Request timeout, rotating key...")
                self._rotate_api_key()
                time.sleep(retry_delay)
                continue

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error: {e}")
                self._rotate_api_key()
                time.sleep(retry_delay)
                continue

        raise RuntimeError("All API keys and models exhausted")

    def _parse_json_response(self, response: str) -> dict:
        """
        Parse JSON from Gemini response, handling markdown code blocks.

        Args:
            response: Raw response text from Gemini.

        Returns:
            Parsed JSON as dictionary.
        """
        # Remove markdown code blocks if present
        text = response.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            self.logger.debug(f"Raw response: {response[:500]}...")
            raise RuntimeError(f"Invalid JSON response from Gemini: {e}")

    def _generate_characters(self, story_text: str) -> list[Character]:
        """
        Generate character descriptions from story text.

        Args:
            story_text: Full story text.

        Returns:
            List of Character objects.
        """
        prompt = f"""
Analyze this story and identify the characters:

---
{story_text[:8000]}
---

Follow the instructions to create character descriptions.
"""

        response = self._call_gemini(prompt, SYSTEM_PROMPT_CHARACTERS)
        data = self._parse_json_response(response)

        characters = []
        for char_data in data.get('characters', []):
            char = Character(
                id=char_data.get('id', 'unknown'),
                role=char_data.get('role', 'supporting'),
                name=char_data.get('name', ''),
                english_prompt=char_data.get('english_prompt', ''),
                vietnamese_prompt=char_data.get('vietnamese_prompt', ''),
                image_file=f"{char_data.get('id', 'unknown')}.png",
                status='pending'
            )
            characters.append(char)

        # Ensure we have at least a main character
        if not any(c.role == 'main' for c in characters):
            self.logger.warning("No main character found, creating default")
            characters.insert(0, Character(
                id='nvc',
                role='main',
                name='Main Character',
                english_prompt='A young adult with kind eyes and warm smile, mid-20s',
                vietnamese_prompt='Nhân vật chính',
                image_file='nvc.png',
                status='pending'
            ))

        return characters

    def _generate_scene_prompts(
        self,
        scenes: list[dict],
        characters: list[Character]
    ) -> dict[int, dict]:
        """
        Generate prompts for all scenes.

        Args:
            scenes: List of scene dictionaries.
            characters: List of Character objects.

        Returns:
            Dictionary mapping scene_id to prompts dict.
        """
        # Build character reference string
        char_descriptions = []
        for char in characters:
            char_descriptions.append(
                f"- {char.id} ({char.name}): {char.english_prompt[:200]}"
            )
        char_ref = "\n".join(char_descriptions)

        # Process scenes in batches to avoid token limits
        batch_size = 10
        all_prompts = {}

        for i in range(0, len(scenes), batch_size):
            batch = scenes[i:i + batch_size]
            self.logger.info(f"Processing scenes {i + 1} to {i + len(batch)}...")

            # Build scene text for this batch
            scene_texts = []
            for scene in batch:
                scene_texts.append(
                    f"Scene {scene['scene_id']} ({scene['start_time']} - {scene['end_time']}):\n"
                    f"{scene['text']}"
                )

            prompt = f"""
CHARACTER REFERENCE:
{char_ref}

SCENES TO PROCESS:
{chr(10).join(scene_texts)}

Create image and video prompts for each scene. Remember:
- Main character MUST reference nvc.png
- Supporting characters MUST reference their respective image files (nvp1.png, etc.)
- Each prompt should describe the scene vividly
- Include mood, lighting, and composition details
"""

            try:
                response = self._call_gemini(prompt, SYSTEM_PROMPT_SCENES)
                data = self._parse_json_response(response)

                for scene_prompt in data.get('scenes', []):
                    scene_id = scene_prompt.get('scene_id')
                    if scene_id:
                        all_prompts[scene_id] = {
                            'img_prompt': scene_prompt.get('img_prompt', ''),
                            'video_prompt': scene_prompt.get('video_prompt', '')
                        }

            except Exception as e:
                self.logger.error(f"Failed to generate prompts for batch: {e}")
                # Create placeholder prompts for failed scenes
                for scene in batch:
                    if scene['scene_id'] not in all_prompts:
                        all_prompts[scene['scene_id']] = {
                            'img_prompt': f"Scene depicting: {scene['text'][:100]}...",
                            'video_prompt': "Slow camera movement with gentle motion"
                        }

            # Rate limiting between batches
            if i + batch_size < len(scenes):
                time.sleep(2)

        return all_prompts

    def regenerate_single_scene(
        self,
        project_dir: Path,
        scene_id: int,
        additional_instructions: str = ""
    ) -> dict:
        """
        Regenerate prompts for a single scene.

        Args:
            project_dir: Path to project directory.
            scene_id: ID of scene to regenerate.
            additional_instructions: Extra instructions for Gemini.

        Returns:
            Dictionary with new img_prompt and video_prompt.
        """
        project_dir = Path(project_dir)
        code = project_dir.name

        # Load workbook
        excel_path = project_dir / "prompts" / f"{code}_prompts.xlsx"
        workbook = PromptWorkbook(self.logger)
        workbook.load_or_create(excel_path)

        # Get existing data
        characters = workbook.get_characters()
        scenes = workbook.get_scenes()

        target_scene = None
        for scene in scenes:
            if scene.scene_id == scene_id:
                target_scene = scene
                break

        if not target_scene:
            raise ValueError(f"Scene {scene_id} not found")

        # Build prompt
        char_descriptions = [f"- {c.id}: {c.english_prompt[:200]}" for c in characters]

        prompt = f"""
CHARACTERS:
{chr(10).join(char_descriptions)}

SCENE {scene_id}:
Time: {target_scene.srt_start} - {target_scene.srt_end}
Text: {target_scene.srt_text}

{additional_instructions if additional_instructions else ""}

Create new image and video prompts for this scene.
Remember to reference character image files (nvc.png, nvp1.png, etc.)
"""

        response = self._call_gemini(prompt, SYSTEM_PROMPT_SCENES)
        data = self._parse_json_response(response)

        scene_data = data.get('scenes', [{}])[0]

        new_img_prompt = scene_data.get('img_prompt', '')
        new_video_prompt = scene_data.get('video_prompt', '')

        # Update workbook
        workbook.update_scene(
            scene_id,
            img_prompt=new_img_prompt,
            video_prompt=new_video_prompt
        )
        workbook.save()

        self.logger.info(f"Regenerated prompts for scene {scene_id}")

        return {
            'img_prompt': new_img_prompt,
            'video_prompt': new_video_prompt
        }
