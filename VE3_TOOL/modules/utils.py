"""
Utility functions for VE3 Tool
==============================

This module provides common utility functions used across the project:
- Logging setup
- Path utilities
- SRT parsing
- Configuration loading
"""

import logging
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import yaml


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SrtEntry:
    """Represents a single subtitle entry from an SRT file."""
    index: int
    start_time: str
    end_time: str
    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class Settings:
    """Application settings loaded from YAML configuration."""
    project_root: str
    gemini_api_key: str
    gemini_model: str
    flowslab_base_url: str
    browser: str
    headless: bool
    implicit_wait: int
    max_scenes_per_account: int
    max_retries: int
    retry_delay: int
    whisper_model: str
    min_scene_duration: int
    max_scene_duration: int
    log_level: str

    @classmethod
    def from_dict(cls, data: dict) -> 'Settings':
        """Create Settings from dictionary, with validation."""
        required_keys = [
            'project_root', 'gemini_api_key', 'gemini_model',
            'flowslab_base_url', 'browser'
        ]

        missing_keys = [k for k in required_keys if k not in data]
        if missing_keys:
            raise ValueError(
                f"Missing required configuration keys: {', '.join(missing_keys)}\n"
                f"Please check your config/settings.yaml file."
            )

        return cls(
            project_root=data['project_root'],
            gemini_api_key=data['gemini_api_key'],
            gemini_model=data.get('gemini_model', 'gemini-1.5-flash'),
            flowslab_base_url=data['flowslab_base_url'],
            browser=data.get('browser', 'chrome'),
            headless=data.get('headless', False),
            implicit_wait=data.get('implicit_wait', 10),
            max_scenes_per_account=data.get('max_scenes_per_account', 50),
            max_retries=data.get('max_retries', 3),
            retry_delay=data.get('retry_delay', 5),
            whisper_model=data.get('whisper_model', 'base'),
            min_scene_duration=data.get('min_scene_duration', 15),
            max_scene_duration=data.get('max_scene_duration', 25),
            log_level=data.get('log_level', 'INFO'),
        )


# ============================================================================
# Logging Functions
# ============================================================================

def setup_logging(
    log_file: Optional[Path] = None,
    level: str = "INFO",
    logger_name: str = "ve3_tool"
) -> logging.Logger:
    """
    Configure logging to output to both console and file.

    Args:
        log_file: Path to the log file. If None, only console logging is enabled.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        logger_name: Name for the logger instance.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "ve3_tool") -> logging.Logger:
    """Get the configured logger instance."""
    return logging.getLogger(name)


# ============================================================================
# Path Utilities
# ============================================================================

def get_project_dir(project_root: Path, code: str) -> Path:
    """
    Get the project directory path for a given project code.

    Args:
        project_root: Root directory of the VE3 tool.
        code: Project code (e.g., "KA1-0001").

    Returns:
        Path to the project directory.
    """
    return Path(project_root) / "PROJECTS" / code


def ensure_project_structure(project_dir: Path, code: str) -> dict[str, Path]:
    """
    Ensure all required subdirectories exist for a project.

    Args:
        project_dir: Path to the project directory.
        code: Project code.

    Returns:
        Dictionary with paths to all subdirectories.
    """
    subdirs = {
        'srt': project_dir / 'srt',
        'prompts': project_dir / 'prompts',
        'nv': project_dir / 'nv',
        'img': project_dir / 'img',
        'vid': project_dir / 'vid',
        'logs': project_dir / 'logs',
    }

    for subdir in subdirs.values():
        subdir.mkdir(parents=True, exist_ok=True)

    return subdirs


def find_voice_file(project_dir: Path, code: str) -> Optional[Path]:
    """
    Find the voice file (mp3 or wav) in the project directory.

    Args:
        project_dir: Path to the project directory.
        code: Project code.

    Returns:
        Path to the voice file, or None if not found.
    """
    for ext in ['.mp3', '.wav']:
        voice_path = project_dir / f"{code}{ext}"
        if voice_path.exists():
            return voice_path
    return None


# ============================================================================
# Configuration Loading
# ============================================================================

def load_settings(config_path: Optional[Path] = None) -> Settings:
    """
    Load settings from YAML configuration file.

    Args:
        config_path: Path to settings.yaml. If None, uses default location.

    Returns:
        Settings object with validated configuration.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If required keys are missing.
    """
    if config_path is None:
        # Try to find config relative to script location
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "settings.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please create a settings.yaml file in the config/ directory."
        )

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    return Settings.from_dict(data)


# ============================================================================
# SRT Parsing
# ============================================================================

def time_to_seconds(time_str: str) -> float:
    """
    Convert SRT time format to seconds.

    Args:
        time_str: Time string in format "HH:MM:SS,mmm" or "HH:MM:SS.mmm"

    Returns:
        Time in seconds as float.
    """
    # Normalize separator
    time_str = time_str.replace(',', '.')

    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    else:
        return float(time_str)


def seconds_to_srt_time(seconds: float) -> str:
    """
    Convert seconds to SRT time format.

    Args:
        seconds: Time in seconds.

    Returns:
        Time string in format "HH:MM:SS,mmm"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    milliseconds = int((secs % 1) * 1000)
    secs = int(secs)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def parse_srt(srt_path: Path) -> list[SrtEntry]:
    """
    Parse an SRT file into a list of SrtEntry objects.

    Args:
        srt_path: Path to the SRT file.

    Returns:
        List of SrtEntry objects containing subtitle data.

    Raises:
        FileNotFoundError: If SRT file doesn't exist.
        ValueError: If SRT format is invalid.
    """
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = []

    # Split by blank lines (double newline)
    blocks = re.split(r'\n\s*\n', content.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        try:
            # First line: index
            index = int(lines[0].strip())

            # Second line: timestamps
            time_match = re.match(
                r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})',
                lines[1].strip()
            )
            if not time_match:
                continue

            start_time = time_match.group(1)
            end_time = time_match.group(2)

            # Rest: subtitle text
            text = '\n'.join(lines[2:]).strip()

            entries.append(SrtEntry(
                index=index,
                start_time=start_time,
                end_time=end_time,
                start_seconds=time_to_seconds(start_time),
                end_seconds=time_to_seconds(end_time),
                text=text
            ))
        except (ValueError, IndexError) as e:
            # Skip malformed entries
            continue

    return entries


def group_srt_into_scenes(
    entries: list[SrtEntry],
    min_duration: float = 15.0,
    max_duration: float = 25.0
) -> list[dict]:
    """
    Group SRT entries into scenes based on duration.

    Args:
        entries: List of SrtEntry objects.
        min_duration: Minimum scene duration in seconds.
        max_duration: Maximum scene duration in seconds.

    Returns:
        List of scene dictionaries with keys:
        - scene_id: Scene number
        - start_time: Start time string
        - end_time: End time string
        - start_seconds: Start time in seconds
        - end_seconds: End time in seconds
        - text: Combined text from all entries in scene
        - entries: List of SrtEntry objects in scene
    """
    if not entries:
        return []

    scenes = []
    current_scene = {
        'entries': [],
        'start_seconds': entries[0].start_seconds,
        'text_parts': []
    }

    for entry in entries:
        current_duration = entry.end_seconds - current_scene['start_seconds']

        # Check if we should start a new scene
        should_split = False

        if current_duration >= max_duration:
            should_split = True
        elif current_duration >= min_duration:
            # Check for natural break points (sentence endings)
            if current_scene['text_parts']:
                last_text = current_scene['text_parts'][-1]
                if last_text.rstrip().endswith(('.', '!', '?', '。', '！', '？')):
                    should_split = True

        if should_split and current_scene['entries']:
            # Finalize current scene
            last_entry = current_scene['entries'][-1]
            scenes.append({
                'scene_id': len(scenes) + 1,
                'start_time': seconds_to_srt_time(current_scene['start_seconds']),
                'end_time': last_entry.end_time,
                'start_seconds': current_scene['start_seconds'],
                'end_seconds': last_entry.end_seconds,
                'text': ' '.join(current_scene['text_parts']),
                'entries': current_scene['entries']
            })

            # Start new scene
            current_scene = {
                'entries': [],
                'start_seconds': entry.start_seconds,
                'text_parts': []
            }

        current_scene['entries'].append(entry)
        current_scene['text_parts'].append(entry.text)

    # Don't forget the last scene
    if current_scene['entries']:
        last_entry = current_scene['entries'][-1]
        scenes.append({
            'scene_id': len(scenes) + 1,
            'start_time': seconds_to_srt_time(current_scene['start_seconds']),
            'end_time': last_entry.end_time,
            'start_seconds': current_scene['start_seconds'],
            'end_seconds': last_entry.end_seconds,
            'text': ' '.join(current_scene['text_parts']),
            'entries': current_scene['entries']
        })

    return scenes


# ============================================================================
# Miscellaneous Utilities
# ============================================================================

def sanitize_filename(name: str) -> str:
    """
    Sanitize a string to be used as a filename.

    Args:
        name: Original string.

    Returns:
        Sanitized string safe for use as filename.
    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')

    # Remove leading/trailing spaces and dots
    name = name.strip(' .')

    # Limit length
    if len(name) > 200:
        name = name[:200]

    return name or 'unnamed'


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like "1h 23m 45s" or "23m 45s".
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return ' '.join(parts)
