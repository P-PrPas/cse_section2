"""
Document retrieval module using Playwright.
Provides a background thread that maintains a persistent browser session
to the OCSC registration system. It listens for National ID queries via a queue,
performs the search, and emits the resulting cropped applicant image as a PyQT signal.
"""

import os
import re
import queue
import logging
import time

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

SEARCH_INPUT_SELECTOR = '#CitizenId, input[name="CitizenId"], input[formcontrolname="CitizenId"]'
SEARCH_BUTTON_SELECTOR = 'button.btn-success:has-text("ค้นหา"), button:has-text("ค้นหา"), input[value="ค้นหา"], a:has-text("ค้นหา")'
RESULT_CARD_SELECTOR = "div.card.shadow"


class ScraperStatus:
    STARTING = "STARTING"
    LOGGING_IN = "LOGGING_IN"
    READY = "READY"
    PROCESSING = "PROCESSING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class OcscScraperThread(QThread):
    """
    Background thread running a persistent Playwright session.
    Accepts National IDs via a thread-safe Queue and emits the screen-grab.
    """

    status_changed = pyqtSignal(str, str)
    search_finished = pyqtSignal(str, object, str)

    def __init__(self, username, password, parent=None):
        super().__init__(parent)
        self.username = username
        self.password = password
        self._request_queue = queue.Queue()
        self._running = True

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def enqueue_search(self, national_id: str):
        """Called from the main thread to push a new search request."""
        self._request_queue.put(national_id)

    def stop(self):
        """Called from the main thread to stop the scraper loop."""
        self._running = False
        self._request_queue.put(None)

    def run(self):
        """Main event loop for the Playwright scraper thread."""
        logger.info("Initializing Playwright Scraper Thread...")
        self.status_changed.emit(ScraperStatus.STARTING, "Initializing Web Scraper Engine")

        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            self._page = self._context.new_page()

            if not self._login():
                self.status_changed.emit(ScraperStatus.FATAL, "Login failed. Check credentials or network.")
                self._cleanup()
                return

            self.status_changed.emit(ScraperStatus.READY, "System Online and Ready to Scan")

            while self._running:
                try:
                    national_id = self._request_queue.get(timeout=1.0)
                    if national_id is None:
                        break

                    self.status_changed.emit(ScraperStatus.PROCESSING, f"Searching ID: {national_id}")
                    img, err = self._perform_search(national_id)
                    self.search_finished.emit(national_id, img, err)

                    if not err:
                        self.status_changed.emit(ScraperStatus.READY, "Waiting for Next Scanner Input")
                    else:
                        self.status_changed.emit(ScraperStatus.ERROR, f"Error: {err}")

                except queue.Empty:
                    continue

        except Exception as e:
            logger.error(f"Fatal Scraper Error: {e}", exc_info=True)
            self.status_changed.emit(ScraperStatus.FATAL, f"Scraper Exception: {str(e)}")

        finally:
            self._cleanup()

    def _login(self) -> bool:
        """Execute the login workflow."""
        self.status_changed.emit(ScraperStatus.LOGGING_IN, "Authenticating with OCSC Portal...")
        try:
            url = "https://job3.ocsc.go.th/OCSRegisterWeb/checkphoto"
            logger.info(f"Navigating to {url}")
            self._page.goto(url, wait_until="networkidle", timeout=15000)

            try:
                username_input = self._page.locator(
                    'input[formcontrolname="userName"], input[type="email"], input[type="text"]'
                ).first
                password_input = self._page.locator(
                    'input[formcontrolname="password"], input[type="password"]'
                ).first

                if username_input.count() > 0 and password_input.count() > 0:
                    logger.info("Filling login credentials")
                    username_input.fill(self.username)
                    password_input.fill(self.password)

                    login_btn = self._page.locator(
                        'button:has-text("เข้าสู่ระบบ"), input[type="submit"], button[type="submit"]'
                    ).first
                    if login_btn.count() > 0:
                        login_btn.click()
                        self._page.wait_for_load_state("networkidle")
            except Exception as login_err:
                logger.warning(
                    "Login form not found explicitly, might already be logged in or page structure is different: %s",
                    login_err,
                )

            self._page.wait_for_timeout(2000)

            search_btn = self._page.locator(SEARCH_BUTTON_SELECTOR).first
            search_input = self._page.locator(SEARCH_INPUT_SELECTOR)
            if search_input.count() == 0:
                search_input = self._page.locator('input[type="text"], input[name*="id"], input[name*="card"]')

            if search_btn.count() > 0 or search_input.count() > 0:
                logger.info("Login verified successful.")
                return True

            logger.error("Could not verify login success. Post-login elements not found.")
            return False

        except PlaywrightTimeoutError:
            logger.error("Timeout during login workflow.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}")
            return False

    def _perform_search(self, national_id: str):
        """Runs the search for a specific national ID and retrieves the image."""
        try:
            search_input = self._page.locator(SEARCH_INPUT_SELECTOR).first
            if search_input.count() == 0:
                search_input = self._page.locator('input[type="text"], input[name*="id"], input[name*="card"]').first

            if search_input.count() == 0:
                return None, "Search text box not found on page."

            search_input.fill(national_id)

            search_btn = self._page.locator(SEARCH_BUTTON_SELECTOR).first
            if search_btn.count() == 0:
                search_input.press("Enter")
            else:
                search_btn.click()

            self._page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1.0)

            not_found = self._page.locator('text="ไม่พบข้อมูล"').count()
            if not_found > 0:
                search_input.fill("")
                return None, "Applicant data not found."

            result_card = self._find_result_card()
            photo_elem = self._find_best_photo_element()

            if photo_elem is not None:
                screenshot_bytes = photo_elem.screenshot(type="png")
            elif result_card is not None:
                screenshot_bytes = result_card.screenshot(type="png")
            else:
                screenshot_bytes = self._page.screenshot(type="png", full_page=False)

            img_array = np.frombuffer(screenshot_bytes, dtype=np.uint8)
            img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if img_bgr is None:
                search_input.fill("")
                return None, "Decoded screenshot is empty."

            if photo_elem is None:
                img_bgr = self._extract_photo_region_from_fallback(
                    img_bgr,
                    used_result_card=result_card is not None,
                )

            search_input.fill("")
            return img_bgr, None

        except PlaywrightTimeoutError:
            return None, "Timeout waiting for search results."
        except Exception as e:
            logger.error(f"Search flow error: {e}", exc_info=True)
            return None, f"Search error: {str(e)}"

    def _find_result_card(self):
        """
        Locate the first visible result card below the page banner.
        """
        try:
            cards = self._page.locator(RESULT_CARD_SELECTOR)
            for idx in range(cards.count()):
                card = cards.nth(idx)
                bbox = card.bounding_box()
                if bbox is None:
                    continue
                if bbox["y"] < 120 or bbox["height"] < 100:
                    continue
                return card
        except Exception as exc:
            logger.debug("Unable to resolve result card: %s", exc)
        return None

    def _find_best_photo_element(self):
        """
        Score all visible images and choose the one that looks like the applicant photo.
        """
        best_locator = None
        best_score = -1.0

        try:
            images = self._page.locator("img")
            for idx in range(images.count()):
                img = images.nth(idx)
                score = self._score_image_candidate(img)
                if score > best_score:
                    best_score = score
                    best_locator = img
        except Exception as exc:
            logger.debug("Unable to locate applicant photo element: %s", exc)

        return best_locator if best_score > 0 else None

    def _score_image_candidate(self, img_locator):
        """
        Reject header/footer graphics and prefer a portrait image in the result area.
        """
        try:
            bbox = img_locator.bounding_box()
            if bbox is None:
                return -1

            width = bbox["width"]
            height = bbox["height"]
            x = bbox["x"]
            y = bbox["y"]

            if width < 40 or height < 40:
                return -1
            if width > height * 2.0:
                return -1
            if y < 120:
                return -1

            area = width * height
            ratio = width / max(height, 1)
            score = area

            if 0.45 <= ratio <= 1.1:
                score += 15000
            if x > 700:
                score += 12000
            if width <= 180 and height <= 240:
                score += 10000

            return score
        except Exception:
            return -1

    def _extract_photo_region_from_fallback(self, img_bgr, used_result_card=False):
        """
        If we only have a full-card or viewport screenshot, crop the region where the
        applicant photo appears in the OCSC layout.
        """
        h, w = img_bgr.shape[:2]

        if used_result_card:
            x1 = int(w * 0.72)
            x2 = int(w * 0.97)
            y1 = int(h * 0.12)
            y2 = int(h * 0.88)
        else:
            x1 = int(w * 0.62)
            x2 = int(w * 0.95)
            y1 = int(h * 0.18)
            y2 = int(h * 0.72)

        x1 = max(0, min(x1, w - 1))
        x2 = max(x1 + 1, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(y1 + 1, min(y2, h))

        return img_bgr[y1:y2, x1:x2]

    def _cleanup(self):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        logger.info("Scraper resources cleaned up.")
