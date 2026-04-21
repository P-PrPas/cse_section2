"""
EDFVS - Exam Document Face Verification System
Entry point for the application.

Loads configuration from config.json and launches the PyQt5 GUI.
"""

import os

# Prevent OpenBLAS memory allocation issues on limited systems
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import sys
import json
import logging
import tempfile
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow

APP_NAME = "EDFVS"


def get_app_root() -> Path:
    """Return the directory that contains the bundled application files."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


bundled_browser_path = get_app_root() / "ms-playwright"
if bundled_browser_path.exists():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browser_path)


def get_runtime_dir() -> Path:
    """Return a writable per-user directory for runtime files."""
    candidates = []

    local_app_data = os.environ.get("LOCALAPPDATA")
    roaming_app_data = os.environ.get("APPDATA")

    if local_app_data:
        candidates.append(Path(local_app_data) / APP_NAME)
    if roaming_app_data:
        candidates.append(Path(roaming_app_data) / APP_NAME)
    candidates.append(Path(tempfile.gettempdir()) / APP_NAME)

    for runtime_dir in candidates:
        try:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            return runtime_dir
        except OSError:
            continue

    raise RuntimeError("Unable to create a writable runtime directory for EDFVS.")


def configure_logging() -> Path:
    """Configure logging to a writable location and return the log file path."""
    log_path = get_runtime_dir() / "edfvs.log"
    handlers = [logging.FileHandler(log_path, encoding="utf-8")]

    if sys.stdout is not None:
        handlers.insert(0, logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    return log_path


LOG_FILE_PATH = configure_logging()
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.json") -> dict:
    """
    Load configuration from a JSON file.
    Falls back to defaults if the file doesn't exist or is invalid.
    """
    defaults = {
        "camera_index": 0,
        "match_threshold": 0.35,
        "http_timeout": 5,
        "url_pattern": r"^\d{13}$",
        "auto_reset_delay": 3,
        "model_name": "VGG-Face",
        "clahe_clip_limit": 2.0,
        "clahe_grid_size": [8, 8],
    }

    full_path = get_app_root() / config_path

    if not full_path.exists():
        logger.warning("Config file '%s' not found. Using defaults.", full_path)
        return defaults

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        merged = {**defaults, **user_config}
        logger.info("Configuration loaded from '%s'.", full_path)
        return merged

    except (json.JSONDecodeError, IOError) as e:
        logger.error("Failed to load config '%s': %s. Using defaults.", full_path, e)
        return defaults


def main():
    """Application entry point."""
    logger.info("=" * 60)
    logger.info("EDFVS - Starting application...")
    logger.info("=" * 60)
    logger.info("Application root: %s", get_app_root())
    logger.info("Log file: %s", LOG_FILE_PATH)

    config = load_config()
    logger.info("Config: %s", json.dumps(config, indent=2))

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    icon_path = get_app_root() / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    app.setStyle("Fusion")

    window = MainWindow(config=config)
    window.show()

    logger.info("Application window shown. Ready for scanning.")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
