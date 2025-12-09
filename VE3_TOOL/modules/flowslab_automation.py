"""
Flows Lab Automation Module
===========================

This module handles web automation for Flows Lab to generate images and videos.
It uses Selenium WebDriver for browser automation.

IMPORTANT: This module contains placeholder selectors that need to be updated
to match the actual Flows Lab UI. Look for TODO comments.

Usage:
    client = FlowsLabClient(account, settings)
    image_path = client.generate_image_for_scene(scene_row)
    video_path = client.generate_video_for_scene(scene_row, image_path)
    client.close()
"""

import logging
import time
import uuid
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    ElementClickInterceptedException
)

from .utils import Settings, get_logger, sanitize_filename
from .account_manager import Account
from .excel_manager import Scene


# ============================================================================
# Selector Configuration
# ============================================================================
# TODO: Update these selectors to match the actual Flows Lab UI
# Use browser DevTools (F12) to inspect elements and find correct selectors

class Selectors:
    """
    CSS/XPath selectors for Flows Lab UI elements.

    TODO: Update all selectors below to match the actual Flows Lab interface.
    Use browser DevTools to find correct selectors.
    """

    # ----- Login Page -----
    LOGIN_EMAIL_INPUT = "input[type='email'], input[name='email'], #email"
    LOGIN_PASSWORD_INPUT = "input[type='password'], input[name='password'], #password"
    LOGIN_SUBMIT_BUTTON = "button[type='submit'], .login-button, #login-btn"
    LOGIN_SUCCESS_INDICATOR = ".dashboard, .home-page, .user-menu"

    # ----- Navigation -----
    NAV_CREATE_NEW = ".create-new-btn, #create-new, [data-action='create']"
    NAV_PROJECTS = ".projects-link, #projects, [href*='projects']"
    NAV_IMAGE_GEN = ".image-gen-link, #image-generator, [href*='image']"
    NAV_VIDEO_GEN = ".video-gen-link, #video-generator, [href*='video']"

    # ----- Image Generation Page -----
    IMG_PROMPT_TEXTAREA = "textarea.prompt-input, #prompt-text, [name='prompt']"
    IMG_REFERENCE_UPLOAD = "input[type='file'].reference-upload, #ref-image-input"
    IMG_GENERATE_BUTTON = "button.generate-btn, #generate-image, [data-action='generate']"
    IMG_RESULT_CONTAINER = ".generated-image, .result-image, #output-image"
    IMG_DOWNLOAD_BUTTON = ".download-btn, #download-image, [data-action='download']"
    IMG_LOADING_INDICATOR = ".loading, .spinner, .generating"

    # ----- Video Generation Page -----
    VID_SOURCE_IMAGE_UPLOAD = "input[type='file'].source-image, #source-image-input"
    VID_PROMPT_TEXTAREA = "textarea.video-prompt, #video-prompt, [name='video-prompt']"
    VID_GENERATE_BUTTON = "button.generate-video-btn, #generate-video"
    VID_RESULT_CONTAINER = ".generated-video, .result-video, #output-video"
    VID_DOWNLOAD_BUTTON = ".download-video-btn, #download-video"
    VID_LOADING_INDICATOR = ".video-loading, .video-spinner, .video-generating"

    # ----- Common -----
    ERROR_MESSAGE = ".error-message, .alert-error, .error-toast"
    SUCCESS_MESSAGE = ".success-message, .alert-success, .success-toast"
    MODAL_CLOSE = ".modal-close, .close-btn, [data-dismiss='modal']"
    COOKIE_ACCEPT = ".cookie-accept, #accept-cookies, [data-action='accept-cookies']"


# ============================================================================
# FlowsLabClient Class
# ============================================================================

class FlowsLabClient:
    """
    Selenium-based client for Flows Lab automation.

    This class handles:
    - Browser initialization and management
    - Login and session management
    - Image generation from prompts
    - Video generation from images + prompts
    - File downloading

    Attributes:
        account: Account to use for authentication.
        settings: Application settings.
        driver: Selenium WebDriver instance.
        logger: Logger instance.
    """

    def __init__(
        self,
        account: Account,
        settings: Settings,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the FlowsLabClient.

        Args:
            account: Account for authentication.
            settings: Application settings.
            logger: Optional logger instance.
        """
        self.account = account
        self.settings = settings
        self.logger = logger or get_logger("ve3_tool.flowslab")
        self.driver: Optional[webdriver.Chrome | webdriver.Edge] = None
        self.is_logged_in = False

        self._init_driver()

    def _init_driver(self) -> None:
        """Initialize the Selenium WebDriver based on settings."""
        browser_type = self.settings.browser.lower()

        self.logger.info(f"Initializing {browser_type} browser...")

        try:
            if browser_type == "chrome":
                self.driver = self._create_chrome_driver()
            elif browser_type == "edge":
                self.driver = self._create_edge_driver()
            else:
                raise ValueError(f"Unsupported browser: {browser_type}")

            self.driver.implicitly_wait(self.settings.implicit_wait)
            self.logger.info("Browser initialized successfully")

        except WebDriverException as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            raise RuntimeError(
                f"Failed to initialize {browser_type} browser.\n"
                f"Make sure you have the browser and its WebDriver installed.\n"
                f"Error: {e}"
            )

    def _create_chrome_driver(self) -> webdriver.Chrome:
        """Create Chrome WebDriver with configured options."""
        options = webdriver.ChromeOptions()

        # Use profile if specified
        if self.account.profile_dir:
            options.add_argument(f"--user-data-dir={self.account.profile_dir}")

        # Common options
        if self.settings.headless:
            options.add_argument("--headless=new")

        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Download preferences
        options.add_experimental_option("prefs", {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })

        return webdriver.Chrome(options=options)

    def _create_edge_driver(self) -> webdriver.Edge:
        """Create Edge WebDriver with configured options."""
        options = webdriver.EdgeOptions()

        if self.account.profile_dir:
            options.add_argument(f"--user-data-dir={self.account.profile_dir}")

        if self.settings.headless:
            options.add_argument("--headless=new")

        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")

        return webdriver.Edge(options=options)

    def close(self) -> None:
        """Close the browser and clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Browser closed")
            except Exception as e:
                self.logger.warning(f"Error closing browser: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ========================================================================
    # Login Methods
    # ========================================================================

    def login_if_needed(self) -> bool:
        """
        Log in to Flows Lab if not already logged in.

        Returns:
            True if login successful or already logged in.

        TODO: Update selectors in Selectors class to match Flows Lab login page.
        """
        if self.is_logged_in:
            return True

        self.logger.info(f"Logging in as {self.account.email}...")

        try:
            # Navigate to login page
            # TODO: Update this URL to the actual Flows Lab login page
            login_url = f"{self.settings.flowslab_base_url}/login"
            self.driver.get(login_url)
            time.sleep(2)

            # Handle cookie consent if present
            self._handle_cookie_consent()

            # Check if already logged in (e.g., from saved profile)
            if self._check_logged_in():
                self.logger.info("Already logged in (from saved session)")
                self.is_logged_in = True
                return True

            # Find and fill email
            email_input = self._wait_and_find(Selectors.LOGIN_EMAIL_INPUT, timeout=10)
            if not email_input:
                raise RuntimeError("Could not find email input field")

            email_input.clear()
            email_input.send_keys(self.account.email)
            time.sleep(0.5)

            # Find and fill password
            password_input = self._wait_and_find(Selectors.LOGIN_PASSWORD_INPUT)
            if not password_input:
                raise RuntimeError("Could not find password input field")

            password_input.clear()
            password_input.send_keys(self.account.password)
            time.sleep(0.5)

            # Click login button
            login_button = self._wait_and_find(Selectors.LOGIN_SUBMIT_BUTTON)
            if not login_button:
                raise RuntimeError("Could not find login button")

            login_button.click()

            # Wait for login to complete
            time.sleep(3)

            # Verify login success
            if self._check_logged_in():
                self.logger.info("Login successful")
                self.is_logged_in = True
                return True
            else:
                # Check for error message
                error = self._find_element(Selectors.ERROR_MESSAGE)
                error_msg = error.text if error else "Unknown error"
                self.logger.error(f"Login failed: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False

    def _check_logged_in(self) -> bool:
        """
        Check if user is currently logged in.

        TODO: Update the success indicator selector to match Flows Lab.
        """
        try:
            element = self.driver.find_element(
                By.CSS_SELECTOR, Selectors.LOGIN_SUCCESS_INDICATOR
            )
            return element is not None
        except NoSuchElementException:
            return False

    def _handle_cookie_consent(self) -> None:
        """Handle cookie consent popup if present."""
        try:
            cookie_btn = self.driver.find_element(
                By.CSS_SELECTOR, Selectors.COOKIE_ACCEPT
            )
            cookie_btn.click()
            time.sleep(0.5)
            self.logger.debug("Accepted cookie consent")
        except NoSuchElementException:
            pass

    # ========================================================================
    # Image Generation Methods
    # ========================================================================

    def generate_image_for_scene(
        self,
        scene: Scene,
        output_dir: Path,
        reference_images: Optional[list[Path]] = None
    ) -> Optional[Path]:
        """
        Generate an image for a scene using the image prompt.

        Args:
            scene: Scene object with img_prompt.
            output_dir: Directory to save the generated image.
            reference_images: Optional list of reference image paths (nvc.png, etc.)

        Returns:
            Path to the saved image, or None if generation failed.

        TODO: Update selectors in this method to match Flows Lab image generation UI.
        """
        if not self.is_logged_in:
            if not self.login_if_needed():
                return None

        self.logger.info(f"Generating image for scene {scene.scene_id}...")

        try:
            # Navigate to image generation page
            # TODO: Update URL to actual Flows Lab image generation page
            self.driver.get(f"{self.settings.flowslab_base_url}/image-generator")
            time.sleep(2)

            # Upload reference images if provided
            if reference_images:
                self._upload_reference_images(reference_images)

            # Enter prompt
            prompt_input = self._wait_and_find(Selectors.IMG_PROMPT_TEXTAREA, timeout=15)
            if not prompt_input:
                raise RuntimeError("Could not find prompt input")

            prompt_input.clear()
            prompt_input.send_keys(scene.img_prompt)
            time.sleep(0.5)

            # Click generate button
            generate_btn = self._wait_and_find(Selectors.IMG_GENERATE_BUTTON)
            if not generate_btn:
                raise RuntimeError("Could not find generate button")

            generate_btn.click()

            # Wait for generation to complete
            self.logger.info("Waiting for image generation...")
            if not self._wait_for_generation_complete(Selectors.IMG_LOADING_INDICATOR):
                raise RuntimeError("Image generation timed out")

            # Download the generated image
            output_path = output_dir / f"scene_{scene.scene_id:03d}.png"
            if self._download_generated_image(output_path):
                self.logger.info(f"Image saved: {output_path.name}")
                return output_path
            else:
                raise RuntimeError("Failed to download generated image")

        except Exception as e:
            self.logger.error(f"Image generation failed for scene {scene.scene_id}: {e}")
            return None

    def _upload_reference_images(self, image_paths: list[Path]) -> None:
        """
        Upload reference images for character consistency.

        TODO: Update selector and upload logic based on Flows Lab UI.
        """
        try:
            file_input = self._find_element(Selectors.IMG_REFERENCE_UPLOAD)
            if not file_input:
                self.logger.warning("Reference image upload not found, skipping")
                return

            for image_path in image_paths:
                if image_path.exists():
                    file_input.send_keys(str(image_path.absolute()))
                    time.sleep(1)
                    self.logger.debug(f"Uploaded reference: {image_path.name}")

        except Exception as e:
            self.logger.warning(f"Failed to upload reference images: {e}")

    def _download_generated_image(self, output_path: Path) -> bool:
        """
        Download the generated image to the specified path.

        TODO: Implement based on how Flows Lab provides generated images.
        Options: direct download button, right-click save, or screenshot.
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Method 1: Try download button
            download_btn = self._find_element(Selectors.IMG_DOWNLOAD_BUTTON)
            if download_btn:
                download_btn.click()
                time.sleep(2)
                # TODO: Handle download and move file to output_path
                # This depends on browser download settings
                self.logger.debug("Download button clicked")
                return True

            # Method 2: Try to get image source and download
            img_element = self._wait_and_find(Selectors.IMG_RESULT_CONTAINER + " img")
            if img_element:
                img_src = img_element.get_attribute("src")
                if img_src:
                    if img_src.startswith("data:image"):
                        # Base64 encoded image
                        return self._save_base64_image(img_src, output_path)
                    else:
                        # URL - download using requests
                        return self._download_image_url(img_src, output_path)

            # Method 3: Screenshot the result container
            result_container = self._find_element(Selectors.IMG_RESULT_CONTAINER)
            if result_container:
                result_container.screenshot(str(output_path))
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to download image: {e}")
            return False

    def _save_base64_image(self, data_url: str, output_path: Path) -> bool:
        """Save a base64 encoded image."""
        try:
            # Remove the data URL prefix
            header, encoded = data_url.split(",", 1)
            image_data = base64.b64decode(encoded)

            with open(output_path, "wb") as f:
                f.write(image_data)

            return True
        except Exception as e:
            self.logger.error(f"Failed to save base64 image: {e}")
            return False

    def _download_image_url(self, url: str, output_path: Path) -> bool:
        """Download image from URL."""
        try:
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

            return True
        except Exception as e:
            self.logger.error(f"Failed to download image from URL: {e}")
            return False

    # ========================================================================
    # Video Generation Methods
    # ========================================================================

    def generate_video_for_scene(
        self,
        scene: Scene,
        source_image_path: Path,
        output_dir: Path
    ) -> Optional[Path]:
        """
        Generate a video for a scene from an image and video prompt.

        Args:
            scene: Scene object with video_prompt.
            source_image_path: Path to the source image.
            output_dir: Directory to save the generated video.

        Returns:
            Path to the saved video, or None if generation failed.

        TODO: Update selectors to match Flows Lab video generation UI.
        """
        if not self.is_logged_in:
            if not self.login_if_needed():
                return None

        if not source_image_path.exists():
            self.logger.error(f"Source image not found: {source_image_path}")
            return None

        self.logger.info(f"Generating video for scene {scene.scene_id}...")

        try:
            # Navigate to video generation page
            # TODO: Update URL to actual Flows Lab video generation page
            self.driver.get(f"{self.settings.flowslab_base_url}/video-generator")
            time.sleep(2)

            # Upload source image
            file_input = self._wait_and_find(Selectors.VID_SOURCE_IMAGE_UPLOAD, timeout=10)
            if not file_input:
                raise RuntimeError("Could not find source image upload")

            file_input.send_keys(str(source_image_path.absolute()))
            time.sleep(2)

            # Enter video prompt
            prompt_input = self._wait_and_find(Selectors.VID_PROMPT_TEXTAREA)
            if not prompt_input:
                raise RuntimeError("Could not find video prompt input")

            prompt_input.clear()
            prompt_input.send_keys(scene.video_prompt)
            time.sleep(0.5)

            # Click generate button
            generate_btn = self._wait_and_find(Selectors.VID_GENERATE_BUTTON)
            if not generate_btn:
                raise RuntimeError("Could not find generate button")

            generate_btn.click()

            # Wait for generation (videos take longer)
            self.logger.info("Waiting for video generation (this may take a while)...")
            if not self._wait_for_generation_complete(
                Selectors.VID_LOADING_INDICATOR,
                timeout=300  # 5 minutes for video
            ):
                raise RuntimeError("Video generation timed out")

            # Download the generated video
            output_path = output_dir / f"scene_{scene.scene_id:03d}.mp4"
            if self._download_generated_video(output_path):
                self.logger.info(f"Video saved: {output_path.name}")
                return output_path
            else:
                raise RuntimeError("Failed to download generated video")

        except Exception as e:
            self.logger.error(f"Video generation failed for scene {scene.scene_id}: {e}")
            return None

    def _download_generated_video(self, output_path: Path) -> bool:
        """
        Download the generated video.

        TODO: Implement based on how Flows Lab provides generated videos.
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Try download button
            download_btn = self._wait_and_find(Selectors.VID_DOWNLOAD_BUTTON, timeout=10)
            if download_btn:
                download_btn.click()
                time.sleep(3)
                # TODO: Handle download and move file to output_path
                return True

            # Try to get video source
            video_element = self._find_element(Selectors.VID_RESULT_CONTAINER + " video")
            if video_element:
                video_src = video_element.get_attribute("src")
                if video_src and not video_src.startswith("blob:"):
                    return self._download_video_url(video_src, output_path)

            return False

        except Exception as e:
            self.logger.error(f"Failed to download video: {e}")
            return False

    def _download_video_url(self, url: str, output_path: Path) -> bool:
        """Download video from URL."""
        try:
            import requests
            response = requests.get(url, timeout=120, stream=True)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            self.logger.error(f"Failed to download video from URL: {e}")
            return False

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _wait_and_find(
        self,
        selector: str,
        timeout: int = 10,
        by: By = By.CSS_SELECTOR
    ) -> Optional[any]:
        """
        Wait for an element to be present and return it.

        Args:
            selector: CSS selector or XPath.
            timeout: Maximum wait time in seconds.
            by: Locator strategy (CSS_SELECTOR or XPATH).

        Returns:
            WebElement or None if not found.
        """
        try:
            # Handle multiple selector options (comma-separated)
            selectors = [s.strip() for s in selector.split(',')]

            for sel in selectors:
                try:
                    element = WebDriverWait(self.driver, timeout / len(selectors)).until(
                        EC.presence_of_element_located((by, sel))
                    )
                    return element
                except TimeoutException:
                    continue

            return None

        except TimeoutException:
            self.logger.debug(f"Element not found: {selector}")
            return None

    def _find_element(self, selector: str, by: By = By.CSS_SELECTOR) -> Optional[any]:
        """
        Find an element without waiting.

        Args:
            selector: CSS selector or XPath.
            by: Locator strategy.

        Returns:
            WebElement or None if not found.
        """
        selectors = [s.strip() for s in selector.split(',')]

        for sel in selectors:
            try:
                return self.driver.find_element(by, sel)
            except NoSuchElementException:
                continue

        return None

    def _wait_for_generation_complete(
        self,
        loading_selector: str,
        timeout: int = 120
    ) -> bool:
        """
        Wait for generation to complete (loading indicator to disappear).

        Args:
            loading_selector: Selector for loading indicator.
            timeout: Maximum wait time in seconds.

        Returns:
            True if generation completed, False if timed out.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            loading = self._find_element(loading_selector)

            if not loading or not loading.is_displayed():
                # Loading indicator gone - check for result
                time.sleep(1)
                return True

            time.sleep(2)

        return False

    def take_screenshot(self, name: str = "screenshot") -> Path:
        """
        Take a screenshot for debugging.

        Args:
            name: Base name for the screenshot file.

        Returns:
            Path to the saved screenshot.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = Path(f"./debug_screenshots/{filename}")
        filepath.parent.mkdir(parents=True, exist_ok=True)

        self.driver.save_screenshot(str(filepath))
        self.logger.debug(f"Screenshot saved: {filepath}")

        return filepath


# ============================================================================
# Batch Processing Function
# ============================================================================

def process_scenes_batch(
    scenes: list[Scene],
    client: FlowsLabClient,
    img_output_dir: Path,
    vid_output_dir: Path,
    nv_dir: Path,
    max_retries: int = 3
) -> dict[int, dict]:
    """
    Process multiple scenes in batch with retry logic.

    Args:
        scenes: List of Scene objects to process.
        client: FlowsLabClient instance.
        img_output_dir: Directory for generated images.
        vid_output_dir: Directory for generated videos.
        nv_dir: Directory containing character reference images.
        max_retries: Maximum retry attempts per scene.

    Returns:
        Dictionary mapping scene_id to results dict with keys:
        - img_path: Path to generated image (or None)
        - vid_path: Path to generated video (or None)
        - img_status: "done" or "error"
        - vid_status: "done" or "error"
    """
    logger = get_logger("ve3_tool.flowslab")
    results = {}

    # Gather reference images
    reference_images = list(nv_dir.glob("*.png")) if nv_dir.exists() else []

    for scene in scenes:
        scene_result = {
            'img_path': None,
            'vid_path': None,
            'img_status': 'pending',
            'vid_status': 'pending'
        }

        # Generate image with retry
        for attempt in range(max_retries):
            try:
                img_path = client.generate_image_for_scene(
                    scene,
                    img_output_dir,
                    reference_images
                )

                if img_path and img_path.exists():
                    scene_result['img_path'] = str(img_path)
                    scene_result['img_status'] = 'done'
                    break

            except Exception as e:
                logger.warning(
                    f"Scene {scene.scene_id} image attempt {attempt + 1} failed: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(5)

        if scene_result['img_status'] != 'done':
            scene_result['img_status'] = 'error'
            results[scene.scene_id] = scene_result
            continue

        # Generate video with retry
        for attempt in range(max_retries):
            try:
                vid_path = client.generate_video_for_scene(
                    scene,
                    Path(scene_result['img_path']),
                    vid_output_dir
                )

                if vid_path and vid_path.exists():
                    scene_result['vid_path'] = str(vid_path)
                    scene_result['vid_status'] = 'done'
                    break

            except Exception as e:
                logger.warning(
                    f"Scene {scene.scene_id} video attempt {attempt + 1} failed: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(5)

        if scene_result['vid_status'] != 'done':
            scene_result['vid_status'] = 'error'

        results[scene.scene_id] = scene_result

    return results
