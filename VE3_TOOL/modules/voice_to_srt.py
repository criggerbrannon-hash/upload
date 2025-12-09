"""
Voice to SRT Module
===================

This module handles the conversion of audio files (mp3/wav) to SRT subtitle files
using OpenAI's Whisper library for speech recognition.

Usage:
    converter = VoiceToSrt(whisper_model="base")
    converter.convert(input_audio_path, output_srt_path)
"""

import logging
from pathlib import Path
from typing import Optional

from .utils import get_logger, seconds_to_srt_time


class VoiceToSrt:
    """
    Converts audio files to SRT subtitle format using Whisper.

    Attributes:
        model_name: Whisper model to use (tiny, base, small, medium, large).
        model: Loaded Whisper model instance.
        logger: Logger instance for this class.
    """

    def __init__(
        self,
        whisper_model: str = "base",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the VoiceToSrt converter.

        Args:
            whisper_model: Name of the Whisper model to use.
                Options: tiny, base, small, medium, large
            logger: Optional logger instance. If None, creates a new one.

        Raises:
            ImportError: If whisper library is not installed.
        """
        self.model_name = whisper_model
        self.model = None
        self.logger = logger or get_logger("ve3_tool.voice_to_srt")

        # Check if whisper is available
        self._check_whisper_available()

    def _check_whisper_available(self) -> None:
        """
        Check if Whisper library is installed and provide installation instructions.

        Raises:
            ImportError: If whisper is not installed.
        """
        try:
            import whisper  # noqa: F401
        except ImportError:
            raise ImportError(
                "Whisper library is not installed.\n\n"
                "Please install it using one of these methods:\n\n"
                "1. Standard whisper (OpenAI):\n"
                "   pip install openai-whisper\n\n"
                "2. Whisper with timestamps (recommended):\n"
                "   pip install whisper-timestamped\n\n"
                "3. For faster performance with CUDA:\n"
                "   pip install openai-whisper torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118\n\n"
                "Note: You may also need to install ffmpeg:\n"
                "   - Ubuntu/Debian: sudo apt install ffmpeg\n"
                "   - macOS: brew install ffmpeg\n"
                "   - Windows: Download from https://ffmpeg.org/download.html"
            )

    def _load_model(self) -> None:
        """Load the Whisper model if not already loaded."""
        if self.model is not None:
            return

        self.logger.info(f"Loading Whisper model: {self.model_name}")

        try:
            import whisper
            self.model = whisper.load_model(self.model_name)
            self.logger.info(f"Whisper model '{self.model_name}' loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise

    def convert(
        self,
        input_audio_path: Path,
        output_srt_path: Path,
        language: Optional[str] = None
    ) -> Path:
        """
        Convert audio file to SRT subtitle file.

        Args:
            input_audio_path: Path to the input audio file (mp3/wav).
            output_srt_path: Path where the SRT file will be saved.
            language: Optional language code (e.g., 'en', 'vi'). If None, auto-detected.

        Returns:
            Path to the generated SRT file.

        Raises:
            FileNotFoundError: If input audio file doesn't exist.
            RuntimeError: If transcription fails.
        """
        input_audio_path = Path(input_audio_path)
        output_srt_path = Path(output_srt_path)

        # Validate input file
        if not input_audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {input_audio_path}")

        self.logger.info(f"Starting transcription: {input_audio_path.name}")

        # Ensure output directory exists
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)

        # Load model
        self._load_model()

        # Transcribe
        try:
            result = self._transcribe(input_audio_path, language)
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Failed to transcribe audio: {e}")

        # Generate SRT content
        srt_content = self._generate_srt(result)

        # Write to file
        with open(output_srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        self.logger.info(f"SRT file saved: {output_srt_path}")

        return output_srt_path

    def _transcribe(self, audio_path: Path, language: Optional[str] = None) -> dict:
        """
        Transcribe audio using Whisper.

        Args:
            audio_path: Path to audio file.
            language: Optional language code.

        Returns:
            Whisper transcription result dictionary.
        """
        import whisper

        self.logger.info("Transcribing audio (this may take a while)...")

        # Prepare transcription options
        options = {
            'verbose': False,
            'word_timestamps': True,
        }

        if language:
            options['language'] = language

        result = self.model.transcribe(str(audio_path), **options)

        # Log detected language
        detected_lang = result.get('language', 'unknown')
        self.logger.info(f"Detected language: {detected_lang}")

        segment_count = len(result.get('segments', []))
        self.logger.info(f"Transcription complete: {segment_count} segments")

        return result

    def _generate_srt(self, result: dict) -> str:
        """
        Generate SRT content from Whisper transcription result.

        Args:
            result: Whisper transcription result dictionary.

        Returns:
            SRT formatted string.
        """
        segments = result.get('segments', [])
        srt_lines = []

        for i, segment in enumerate(segments, start=1):
            start_time = segment.get('start', 0)
            end_time = segment.get('end', 0)
            text = segment.get('text', '').strip()

            if not text:
                continue

            # Format times
            start_str = seconds_to_srt_time(start_time)
            end_str = seconds_to_srt_time(end_time)

            # Add SRT entry
            srt_lines.append(str(i))
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(text)
            srt_lines.append('')  # Blank line between entries

        return '\n'.join(srt_lines)

    def transcribe_with_timestamps(
        self,
        input_audio_path: Path,
        language: Optional[str] = None
    ) -> list[dict]:
        """
        Transcribe audio and return detailed timestamp information.

        This method is useful when you need more control over the transcription
        data without generating an SRT file.

        Args:
            input_audio_path: Path to the input audio file.
            language: Optional language code.

        Returns:
            List of segment dictionaries with keys:
            - start: Start time in seconds
            - end: End time in seconds
            - text: Transcribed text
            - words: List of word-level timestamps (if available)
        """
        input_audio_path = Path(input_audio_path)

        if not input_audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {input_audio_path}")

        self._load_model()
        result = self._transcribe(input_audio_path, language)

        return result.get('segments', [])


class VoiceToSrtWithTimestamped:
    """
    Alternative implementation using whisper_timestamped for more accurate timestamps.

    This class provides word-level timestamps which can be useful for
    more precise subtitle generation.
    """

    def __init__(
        self,
        whisper_model: str = "base",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize with whisper_timestamped library.

        Args:
            whisper_model: Whisper model name.
            logger: Optional logger instance.

        Raises:
            ImportError: If whisper_timestamped is not installed.
        """
        self.model_name = whisper_model
        self.model = None
        self.logger = logger or get_logger("ve3_tool.voice_to_srt")

        self._check_whisper_timestamped_available()

    def _check_whisper_timestamped_available(self) -> None:
        """Check if whisper_timestamped is available."""
        try:
            import whisper_timestamped  # noqa: F401
        except ImportError:
            raise ImportError(
                "whisper_timestamped library is not installed.\n\n"
                "Install it with:\n"
                "   pip install whisper-timestamped\n"
            )

    def _load_model(self) -> None:
        """Load the Whisper model."""
        if self.model is not None:
            return

        self.logger.info(f"Loading Whisper model (timestamped): {self.model_name}")

        import whisper_timestamped as whisper
        self.model = whisper.load_model(self.model_name)
        self.logger.info("Model loaded successfully")

    def convert(
        self,
        input_audio_path: Path,
        output_srt_path: Path,
        language: Optional[str] = None
    ) -> Path:
        """
        Convert audio to SRT using whisper_timestamped.

        Args:
            input_audio_path: Path to audio file.
            output_srt_path: Path for output SRT file.
            language: Optional language code.

        Returns:
            Path to generated SRT file.
        """
        import whisper_timestamped as whisper

        input_audio_path = Path(input_audio_path)
        output_srt_path = Path(output_srt_path)

        if not input_audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {input_audio_path}")

        self.logger.info(f"Starting transcription: {input_audio_path.name}")

        output_srt_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_model()

        # Load audio
        audio = whisper.load_audio(str(input_audio_path))

        # Transcribe
        options = {}
        if language:
            options['language'] = language

        result = whisper.transcribe(self.model, audio, **options)

        # Generate SRT
        srt_content = self._generate_srt(result)

        with open(output_srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        self.logger.info(f"SRT file saved: {output_srt_path}")

        return output_srt_path

    def _generate_srt(self, result: dict) -> str:
        """Generate SRT content from whisper_timestamped result."""
        segments = result.get('segments', [])
        srt_lines = []

        for i, segment in enumerate(segments, start=1):
            start_time = segment.get('start', 0)
            end_time = segment.get('end', 0)
            text = segment.get('text', '').strip()

            if not text:
                continue

            start_str = seconds_to_srt_time(start_time)
            end_str = seconds_to_srt_time(end_time)

            srt_lines.append(str(i))
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(text)
            srt_lines.append('')

        return '\n'.join(srt_lines)


def create_voice_to_srt(
    whisper_model: str = "base",
    use_timestamped: bool = False,
    logger: Optional[logging.Logger] = None
) -> VoiceToSrt | VoiceToSrtWithTimestamped:
    """
    Factory function to create the appropriate VoiceToSrt instance.

    Args:
        whisper_model: Whisper model name.
        use_timestamped: If True, try to use whisper_timestamped.
        logger: Optional logger instance.

    Returns:
        VoiceToSrt or VoiceToSrtWithTimestamped instance.
    """
    if use_timestamped:
        try:
            return VoiceToSrtWithTimestamped(whisper_model, logger)
        except ImportError:
            # Fall back to standard whisper
            pass

    return VoiceToSrt(whisper_model, logger)
