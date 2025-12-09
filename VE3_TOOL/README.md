# VE3 Tool - Voice to Video Pipeline

A complete Python pipeline for converting voice recordings into video clips with consistent character generation.

## Overview

**Pipeline Flow:**
```
Voice (mp3/wav) → SRT (subtitles) → Prompts (via Gemini AI) → Images & Videos (via Flows Lab)
```

## Features

- **Voice to SRT**: Convert voice recordings to subtitles using Whisper
- **AI Prompt Generation**: Automatically generate image/video prompts using Gemini AI
- **Character Consistency**: Reference-based character generation for consistent visuals
- **Multi-Account Support**: Rotate between multiple Flows Lab accounts
- **Excel Management**: Track all prompts and generation status in Excel files
- **Modular Architecture**: Easy to customize and extend

## Project Structure

```
VE3_TOOL/
├── ve3_tool.py              # Main CLI entry point
├── config/
│   ├── settings.yaml        # Global configuration
│   └── accounts.csv         # Flows Lab account credentials
├── modules/
│   ├── utils.py             # Utility functions
│   ├── voice_to_srt.py      # Voice transcription
│   ├── excel_manager.py     # Excel file management
│   ├── prompts_generator.py # Gemini AI integration
│   ├── account_manager.py   # Account rotation
│   └── flowslab_automation.py # Selenium automation
├── PROJECTS/
│   └── {PROJECT_CODE}/      # Each project has its own folder
│       ├── {CODE}.mp3       # Voice file
│       ├── srt/             # Subtitles
│       ├── prompts/         # Excel with prompts
│       ├── nv/              # Character reference images
│       ├── img/             # Generated images
│       ├── vid/             # Generated videos
│       └── logs/            # Pipeline logs
└── README.md
```

## Installation

### 1. Python Requirements

```bash
# Python 3.10+ required
python --version

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
# Core dependencies
pip install pyyaml openpyxl requests selenium

# Voice transcription (Whisper)
pip install openai-whisper

# For GPU acceleration (optional)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 3. Install FFmpeg

Whisper requires FFmpeg for audio processing:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
# Add to system PATH
```

### 4. Install WebDriver

For Selenium automation:

```bash
# Chrome
# Download ChromeDriver from https://chromedriver.chromium.org/
# Or use webdriver-manager:
pip install webdriver-manager

# Edge
# Download Edge WebDriver from https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/
```

## Configuration

### 1. Gemini API Key

1. Get a free API key at: https://makersuite.google.com/app/apikey
2. Edit `config/settings.yaml`:

```yaml
gemini_api_key: "YOUR_API_KEY_HERE"
gemini_model: "gemini-1.5-flash"
```

### 2. Flows Lab Accounts

Edit `config/accounts.csv`:

```csv
account_name,email,password,profile_dir,cookies_file,active
main_account,your@email.com,yourpassword,,,true
backup_account,backup@email.com,backuppass,,,true
```

### 3. Browser Settings

In `config/settings.yaml`:

```yaml
browser: "chrome"  # or "edge"
headless: false    # Set to true for background operation
```

## Usage

### Basic Commands

```bash
# List all projects
python ve3_tool.py list

# Create a new project
python ve3_tool.py init KA1-0001 /path/to/voice.mp3

# Check project status
python ve3_tool.py status KA1-0001

# Run full pipeline
python ve3_tool.py run KA1-0001 --steps all
```

### Step-by-Step Execution

```bash
# 1. Convert voice to subtitles
python ve3_tool.py run KA1-0001 --steps voice_to_srt

# 2. Generate prompts with AI
python ve3_tool.py run KA1-0001 --steps prompts

# 3. Generate images only
python ve3_tool.py run KA1-0001 --steps image

# 4. Generate videos (requires images)
python ve3_tool.py run KA1-0001 --steps video
```

### Advanced Options

```bash
# Regenerate prompts (overwrite existing)
python ve3_tool.py run KA1-0001 --steps prompts --overwrite-prompts

# Generate only images
python ve3_tool.py run KA1-0001 --steps image --only-image

# Generate only videos
python ve3_tool.py run KA1-0001 --steps video --only-video

# Use custom config file
python ve3_tool.py --config /path/to/settings.yaml run KA1-0001 --steps all
```

## Character Reference Images

For consistent character appearance across scenes:

1. Create character reference images
2. Place them in `PROJECTS/{CODE}/nv/`:
   - `nvc.png` - Main character (nhân vật chính)
   - `nvp1.png` - Supporting character 1
   - `nvp2.png` - Supporting character 2
   - etc.

The AI will reference these images when generating scene prompts.

## Excel File Structure

### Characters Sheet
| Column | Description |
|--------|-------------|
| id | Character ID (nvc, nvp1, etc.) |
| role | main or supporting |
| name | Character name |
| english_prompt | Visual description for AI |
| vietnamese_prompt | Vietnamese description (optional) |
| image_file | Reference image filename |
| status | pending/done/error |

### Scenes Sheet
| Column | Description |
|--------|-------------|
| scene_id | Scene number |
| srt_start | Start timestamp |
| srt_end | End timestamp |
| srt_text | Subtitle text |
| img_prompt | Image generation prompt |
| video_prompt | Video generation prompt |
| img_path | Generated image path |
| video_path | Generated video path |
| status_img | pending/done/error |
| status_vid | pending/done/error |

## Customization

### Flows Lab Selectors

The Selenium automation uses placeholder selectors. To customize for your specific Flows Lab UI:

1. Open `modules/flowslab_automation.py`
2. Find the `Selectors` class
3. Update CSS selectors to match your UI:

```python
class Selectors:
    # Update these to match actual UI
    LOGIN_EMAIL_INPUT = "input#email"
    LOGIN_PASSWORD_INPUT = "input#password"
    IMG_PROMPT_TEXTAREA = "textarea.prompt-box"
    # ... etc.
```

### Scene Grouping

Adjust how subtitles are grouped into scenes in `config/settings.yaml`:

```yaml
min_scene_duration: 15  # seconds
max_scene_duration: 25  # seconds
```

## Troubleshooting

### Whisper Installation Issues

```bash
# If you get CUDA errors, try CPU-only:
pip install openai-whisper

# For better timestamps:
pip install whisper-timestamped
```

### Selenium Issues

```bash
# Update WebDriver
pip install webdriver-manager

# In Python:
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
driver = webdriver.Chrome(ChromeDriverManager().install())
```

### Gemini API Errors

- **Rate limited**: Reduce batch size or add delays
- **Invalid API key**: Check key at https://makersuite.google.com/
- **Model not found**: Try `gemini-1.5-flash` or `gemini-pro`

## Requirements File

Create `requirements.txt`:

```
pyyaml>=6.0
openpyxl>=3.1.0
requests>=2.28.0
selenium>=4.10.0
openai-whisper>=20231117
```

## License

MIT License

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## Support

For issues and feature requests, please create an issue on GitHub.
