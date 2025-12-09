#!/usr/bin/env python3
"""
VE3 Tool - Voice to Video Pipeline
===================================

A complete pipeline tool for converting voice recordings into video clips:
voice -> SRT -> prompts (via Gemini) -> images & videos (via Flows Lab)

Usage:
    python ve3_tool.py list
    python ve3_tool.py init CODE /path/to/voice.mp3
    python ve3_tool.py run CODE --steps all
    python ve3_tool.py run CODE --steps prompts,image

Author: VE3 Tool Team
Version: 1.0.0
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.utils import (
    load_settings,
    setup_logging,
    get_project_dir,
    ensure_project_structure,
    find_voice_file,
    Settings
)
from modules.voice_to_srt import VoiceToSrt, create_voice_to_srt
from modules.excel_manager import PromptWorkbook
from modules.prompts_generator import PromptGenerator
from modules.account_manager import AccountManager
from modules.flowslab_automation import FlowsLabClient, process_scenes_batch


# ============================================================================
# Constants
# ============================================================================

VERSION = "1.0.0"
VALID_STEPS = ['voice_to_srt', 'prompts', 'image', 'video', 'all']


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_list(args, settings: Settings) -> int:
    """
    List all projects and their status.

    Returns:
        Exit code (0 for success).
    """
    projects_dir = Path(settings.project_root) / "PROJECTS"

    if not projects_dir.exists():
        print("No projects found. Use 'init' to create a new project.")
        return 0

    projects = [d for d in projects_dir.iterdir() if d.is_dir()]

    if not projects:
        print("No projects found. Use 'init' to create a new project.")
        return 0

    print("\n" + "=" * 70)
    print(f"{'PROJECT CODE':<15} {'VOICE':<8} {'SRT':<8} {'PROMPTS':<10} {'IMAGES':<10} {'VIDEOS':<10}")
    print("=" * 70)

    for project_dir in sorted(projects):
        code = project_dir.name

        # Check voice file
        voice_exists = find_voice_file(project_dir, code) is not None
        voice_status = "Yes" if voice_exists else "No"

        # Check SRT
        srt_path = project_dir / "srt" / f"{code}.srt"
        srt_status = "Yes" if srt_path.exists() else "No"

        # Check prompts Excel
        excel_path = project_dir / "prompts" / f"{code}_prompts.xlsx"
        prompts_status = "No"
        img_done = vid_done = 0
        total_scenes = 0

        if excel_path.exists():
            try:
                workbook = PromptWorkbook()
                workbook.load_or_create(excel_path)
                stats = workbook.get_statistics()
                total_scenes = stats['total_scenes']
                img_done = stats['images_done']
                vid_done = stats['videos_done']
                prompts_status = f"{stats['scenes_with_img_prompt']}/{total_scenes}"
            except Exception:
                prompts_status = "Error"

        img_status = f"{img_done}/{total_scenes}" if total_scenes > 0 else "0/0"
        vid_status = f"{vid_done}/{total_scenes}" if total_scenes > 0 else "0/0"

        print(f"{code:<15} {voice_status:<8} {srt_status:<8} {prompts_status:<10} {img_status:<10} {vid_status:<10}")

    print("=" * 70 + "\n")

    return 0


def cmd_init(args, settings: Settings) -> int:
    """
    Initialize a new project.

    Args:
        args: Parsed arguments with 'code' and 'voice_path'.
        settings: Application settings.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    code = args.code
    voice_source = Path(args.voice_path)

    if not voice_source.exists():
        print(f"Error: Voice file not found: {voice_source}")
        return 1

    # Validate file extension
    if voice_source.suffix.lower() not in ['.mp3', '.wav']:
        print(f"Error: Voice file must be .mp3 or .wav, got: {voice_source.suffix}")
        return 1

    # Create project directory
    project_dir = get_project_dir(settings.project_root, code)

    if project_dir.exists():
        print(f"Warning: Project '{code}' already exists at {project_dir}")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return 1

    # Create directory structure
    print(f"Creating project: {code}")
    subdirs = ensure_project_structure(project_dir, code)

    # Copy voice file
    voice_dest = project_dir / f"{code}{voice_source.suffix.lower()}"
    print(f"Copying voice file to: {voice_dest.name}")
    shutil.copy2(voice_source, voice_dest)

    # Print summary
    print(f"\nProject initialized successfully!")
    print(f"  Location: {project_dir}")
    print(f"  Voice file: {voice_dest.name}")
    print(f"\nCreated directories:")
    for name, path in subdirs.items():
        print(f"  - {name}/")

    print(f"\nNext steps:")
    print(f"  1. (Optional) Add character reference images to: {subdirs['nv']}/")
    print(f"     Name them: nvc.png, nvp1.png, nvp2.png, ...")
    print(f"  2. Run the pipeline: python ve3_tool.py run {code} --steps all")

    return 0


def cmd_run(args, settings: Settings) -> int:
    """
    Run the pipeline for a project.

    Args:
        args: Parsed arguments with 'code', 'steps', and flags.
        settings: Application settings.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    code = args.code
    project_dir = get_project_dir(settings.project_root, code)

    if not project_dir.exists():
        print(f"Error: Project '{code}' not found.")
        print(f"Use 'init' to create a new project first.")
        return 1

    # Parse steps
    steps_input = args.steps.lower()
    if steps_input == 'all':
        steps = ['voice_to_srt', 'prompts', 'image', 'video']
    else:
        steps = [s.strip() for s in steps_input.split(',')]
        for step in steps:
            if step not in VALID_STEPS:
                print(f"Error: Invalid step '{step}'")
                print(f"Valid steps: {', '.join(VALID_STEPS)}")
                return 1

    # Setup logging
    log_file = project_dir / "logs" / "pipeline.log"
    logger = setup_logging(log_file, settings.log_level)
    logger.info(f"Starting pipeline for project: {code}")
    logger.info(f"Steps: {steps}")

    # Ensure project structure exists
    subdirs = ensure_project_structure(project_dir, code)

    try:
        # Step 1: Voice to SRT
        if 'voice_to_srt' in steps:
            success = run_voice_to_srt(project_dir, code, settings, logger)
            if not success:
                return 1

        # Step 2: Generate Prompts
        if 'prompts' in steps:
            success = run_prompts_generator(
                project_dir, code, settings, logger,
                overwrite=args.overwrite_prompts
            )
            if not success:
                return 1

        # Step 3 & 4: Generate Images and Videos
        if 'image' in steps or 'video' in steps:
            success = run_media_generation(
                project_dir, code, settings, logger,
                generate_images='image' in steps,
                generate_videos='video' in steps,
                only_image=args.only_image,
                only_video=args.only_video
            )
            if not success:
                return 1

        logger.info("Pipeline completed successfully!")
        print(f"\nPipeline completed for project: {code}")

        return 0

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        print(f"\nError: {e}")
        return 1


def run_voice_to_srt(
    project_dir: Path,
    code: str,
    settings: Settings,
    logger
) -> bool:
    """
    Run voice to SRT conversion step.

    Returns:
        True if successful.
    """
    srt_path = project_dir / "srt" / f"{code}.srt"

    if srt_path.exists():
        logger.info(f"SRT file already exists: {srt_path.name}")
        print(f"SRT file already exists: {srt_path.name}")
        return True

    voice_path = find_voice_file(project_dir, code)
    if not voice_path:
        logger.error("Voice file not found")
        print("Error: Voice file not found in project directory")
        return False

    print(f"Converting voice to SRT: {voice_path.name}")
    logger.info(f"Converting voice to SRT: {voice_path.name}")

    try:
        converter = create_voice_to_srt(
            whisper_model=settings.whisper_model,
            use_timestamped=False,
            logger=logger
        )

        converter.convert(voice_path, srt_path)

        print(f"SRT file created: {srt_path.name}")
        return True

    except ImportError as e:
        logger.error(str(e))
        print(f"\nError: {e}")
        return False

    except Exception as e:
        logger.error(f"Voice to SRT failed: {e}")
        print(f"Error during transcription: {e}")
        return False


def run_prompts_generator(
    project_dir: Path,
    code: str,
    settings: Settings,
    logger,
    overwrite: bool = False
) -> bool:
    """
    Run prompts generation step.

    Returns:
        True if successful.
    """
    excel_path = project_dir / "prompts" / f"{code}_prompts.xlsx"

    if excel_path.exists() and not overwrite:
        workbook = PromptWorkbook(logger)
        workbook.load_or_create(excel_path)

        if workbook.has_prompts():
            logger.info("Prompts already exist in Excel")
            print("Prompts already exist. Use --overwrite-prompts to regenerate.")
            return True

    srt_path = project_dir / "srt" / f"{code}.srt"
    if not srt_path.exists():
        logger.error("SRT file not found")
        print("Error: SRT file not found. Run voice_to_srt step first.")
        return False

    print("Generating prompts with Gemini AI...")
    logger.info("Starting prompt generation with Gemini")

    try:
        generator = PromptGenerator(settings, logger)
        workbook = generator.generate_for_project(project_dir, overwrite=overwrite)

        stats = workbook.get_statistics()
        print(f"Generated prompts for {stats['total_scenes']} scenes")
        print(f"Identified {stats['total_characters']} characters")

        return True

    except ValueError as e:
        logger.error(str(e))
        print(f"\nConfiguration Error: {e}")
        return False

    except Exception as e:
        logger.error(f"Prompt generation failed: {e}")
        print(f"Error during prompt generation: {e}")
        return False


def run_media_generation(
    project_dir: Path,
    code: str,
    settings: Settings,
    logger,
    generate_images: bool = True,
    generate_videos: bool = True,
    only_image: bool = False,
    only_video: bool = False
) -> bool:
    """
    Run image and/or video generation step using Flows Lab.

    Returns:
        True if successful (or partially successful).
    """
    # Load Excel data
    excel_path = project_dir / "prompts" / f"{code}_prompts.xlsx"
    if not excel_path.exists():
        logger.error("Prompts Excel file not found")
        print("Error: Prompts file not found. Run prompts step first.")
        return False

    workbook = PromptWorkbook(logger)
    workbook.load_or_create(excel_path)

    scenes = workbook.get_scenes()
    if not scenes:
        logger.warning("No scenes found in Excel")
        print("No scenes found in prompts file.")
        return True

    # Filter scenes based on flags
    if only_image:
        generate_videos = False
    if only_video:
        generate_images = False

    # Get scenes that need processing
    scenes_for_img = []
    scenes_for_vid = []

    if generate_images:
        scenes_for_img = [s for s in scenes if s.status_img != 'done']
        print(f"Images to generate: {len(scenes_for_img)}/{len(scenes)}")

    if generate_videos:
        scenes_for_vid = [s for s in scenes if s.status_vid != 'done' and s.img_path]
        print(f"Videos to generate: {len(scenes_for_vid)}/{len(scenes)}")

    if not scenes_for_img and not scenes_for_vid:
        print("All media already generated.")
        return True

    # Load account manager
    accounts_path = Path(settings.project_root) / "config" / "accounts.csv"
    try:
        account_manager = AccountManager(
            accounts_path,
            max_scenes_per_account=settings.max_scenes_per_account,
            logger=logger
        )
    except FileNotFoundError:
        logger.error("Accounts file not found")
        print(f"Error: Accounts file not found: {accounts_path}")
        print("Create an accounts.csv file with your Flows Lab credentials.")
        return False

    # Get directories
    img_dir = project_dir / "img"
    vid_dir = project_dir / "vid"
    nv_dir = project_dir / "nv"

    # Process with account rotation
    total_processed = 0
    errors = 0

    while scenes_for_img or scenes_for_vid:
        account = account_manager.get_next_active_account()
        if not account:
            logger.warning("No more usable accounts available")
            print("Warning: All accounts exhausted or have errors")
            break

        print(f"\nUsing account: {account.account_name}")

        try:
            with FlowsLabClient(account, settings, logger) as client:
                # Login
                if not client.login_if_needed():
                    account_manager.mark_login_status(account.account_name, success=False)
                    continue

                account_manager.mark_login_status(account.account_name, success=True)

                # Process scenes up to account limit
                scenes_this_account = 0
                max_per_account = settings.max_scenes_per_account

                # Process images
                while scenes_for_img and scenes_this_account < max_per_account:
                    scene = scenes_for_img.pop(0)

                    # Get reference images
                    ref_images = list(nv_dir.glob("*.png")) if nv_dir.exists() else []

                    img_path = client.generate_image_for_scene(
                        scene, img_dir, ref_images
                    )

                    if img_path:
                        workbook.update_scene(
                            scene.scene_id,
                            img_path=str(img_path),
                            status_img='done'
                        )
                        print(f"  Scene {scene.scene_id}: Image OK")

                        # Add to video queue if needed
                        if generate_videos and scene not in scenes_for_vid:
                            scene.img_path = str(img_path)
                            scenes_for_vid.append(scene)
                    else:
                        workbook.update_scene(scene.scene_id, status_img='error')
                        account_manager.mark_account_error(
                            account.account_name, f"Scene {scene.scene_id} image failed"
                        )
                        errors += 1
                        print(f"  Scene {scene.scene_id}: Image FAILED")

                    workbook.save()
                    account_manager.mark_account_used(account.account_name)
                    scenes_this_account += 1
                    total_processed += 1

                # Process videos
                while scenes_for_vid and scenes_this_account < max_per_account:
                    scene = scenes_for_vid.pop(0)

                    if not scene.img_path:
                        continue

                    vid_path = client.generate_video_for_scene(
                        scene, Path(scene.img_path), vid_dir
                    )

                    if vid_path:
                        workbook.update_scene(
                            scene.scene_id,
                            video_path=str(vid_path),
                            status_vid='done'
                        )
                        print(f"  Scene {scene.scene_id}: Video OK")
                    else:
                        workbook.update_scene(scene.scene_id, status_vid='error')
                        account_manager.mark_account_error(
                            account.account_name, f"Scene {scene.scene_id} video failed"
                        )
                        errors += 1
                        print(f"  Scene {scene.scene_id}: Video FAILED")

                    workbook.save()
                    account_manager.mark_account_used(account.account_name)
                    scenes_this_account += 1
                    total_processed += 1

        except Exception as e:
            logger.error(f"Error with account {account.account_name}: {e}")
            account_manager.mark_account_error(account.account_name, str(e))

    # Final summary
    print(f"\nMedia generation complete:")
    print(f"  Processed: {total_processed}")
    print(f"  Errors: {errors}")

    account_manager.print_status()

    return errors == 0


def cmd_status(args, settings: Settings) -> int:
    """
    Show detailed status for a project.

    Args:
        args: Parsed arguments with 'code'.
        settings: Application settings.

    Returns:
        Exit code.
    """
    code = args.code
    project_dir = get_project_dir(settings.project_root, code)

    if not project_dir.exists():
        print(f"Error: Project '{code}' not found.")
        return 1

    print(f"\n{'=' * 60}")
    print(f"PROJECT STATUS: {code}")
    print(f"{'=' * 60}")

    # Check files
    voice_file = find_voice_file(project_dir, code)
    srt_path = project_dir / "srt" / f"{code}.srt"
    excel_path = project_dir / "prompts" / f"{code}_prompts.xlsx"

    print(f"\nFiles:")
    print(f"  Voice file: {'Yes' if voice_file else 'No'}")
    print(f"  SRT file:   {'Yes' if srt_path.exists() else 'No'}")
    print(f"  Excel file: {'Yes' if excel_path.exists() else 'No'}")

    # Character reference images
    nv_dir = project_dir / "nv"
    nv_files = list(nv_dir.glob("*.png")) if nv_dir.exists() else []
    print(f"\nCharacter references ({len(nv_files)} files):")
    for f in nv_files[:5]:
        print(f"  - {f.name}")
    if len(nv_files) > 5:
        print(f"  ... and {len(nv_files) - 5} more")

    # Excel statistics
    if excel_path.exists():
        try:
            workbook = PromptWorkbook()
            workbook.load_or_create(excel_path)
            stats = workbook.get_statistics()

            print(f"\nPrompts & Generation Status:")
            print(f"  Characters: {stats['total_characters']}")
            print(f"  Scenes: {stats['total_scenes']}")
            print(f"  Scenes with prompts: {stats['scenes_with_img_prompt']}")
            print(f"\n  Images:")
            print(f"    Done:    {stats['images_done']}")
            print(f"    Pending: {stats['images_pending']}")
            print(f"    Error:   {stats['images_error']}")
            print(f"\n  Videos:")
            print(f"    Done:    {stats['videos_done']}")
            print(f"    Pending: {stats['videos_pending']}")
            print(f"    Error:   {stats['videos_error']}")

        except Exception as e:
            print(f"\nError reading Excel: {e}")

    print(f"\n{'=' * 60}\n")

    return 0


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="VE3 Tool - Voice to Video Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                           List all projects
  %(prog)s init KA1-0001 ./voice.mp3      Initialize new project
  %(prog)s run KA1-0001 --steps all       Run full pipeline
  %(prog)s run KA1-0001 --steps prompts   Generate prompts only
  %(prog)s status KA1-0001                Show project status
        """
    )

    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'VE3 Tool {VERSION}'
    )

    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to settings.yaml config file'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all projects')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new project')
    init_parser.add_argument('code', help='Project code (e.g., KA1-0001)')
    init_parser.add_argument('voice_path', help='Path to voice file (mp3/wav)')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run pipeline for a project')
    run_parser.add_argument('code', help='Project code')
    run_parser.add_argument(
        '--steps', '-s',
        default='all',
        help='Steps to run: all, voice_to_srt, prompts, image, video (comma-separated)'
    )
    run_parser.add_argument(
        '--overwrite-prompts',
        action='store_true',
        help='Regenerate prompts even if they exist'
    )
    run_parser.add_argument(
        '--only-image',
        action='store_true',
        help='Only generate images, skip videos'
    )
    run_parser.add_argument(
        '--only-video',
        action='store_true',
        help='Only generate videos (requires existing images)'
    )

    # Status command
    status_parser = subparsers.add_parser('status', help='Show project status')
    status_parser.add_argument('code', help='Project code')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Load settings
    try:
        config_path = args.config if args.config else None
        settings = load_settings(config_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"Configuration Error: {e}")
        return 1

    # Execute command
    if args.command == 'list':
        return cmd_list(args, settings)
    elif args.command == 'init':
        return cmd_init(args, settings)
    elif args.command == 'run':
        return cmd_run(args, settings)
    elif args.command == 'status':
        return cmd_status(args, settings)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
