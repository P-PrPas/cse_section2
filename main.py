"""
EDFVS — Exam Document Face Verification System
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

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from ui.main_window import MainWindow

# ── Logging Configuration ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("edfvs.log", encoding="utf-8")
    ]
)
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
        "clahe_grid_size": [8, 8]
    }

    # Resolve path relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, config_path)

    if not os.path.exists(full_path):
        logger.warning(
            "Config file '%s' not found. Using defaults.", full_path
        )
        return defaults

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        # Merge: user config overrides defaults
        merged = {**defaults, **user_config}
        logger.info("Configuration loaded from '%s'.", full_path)
        return merged

    except (json.JSONDecodeError, IOError) as e:
        logger.error(
            "Failed to load config '%s': %s. Using defaults.", full_path, e
        )
        return defaults


def main():
    """Application entry point."""
    logger.info("=" * 60)
    logger.info("EDFVS — Starting application...")
    logger.info("=" * 60)

    config = load_config()
    logger.info("Config: %s", json.dumps(config, indent=2))

    app = QApplication(sys.argv)
    app.setApplicationName("EDFVS")

    # Set app icon if available
    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png"
    )
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Set global font
    app.setStyle("Fusion")

    window = MainWindow(config=config)
    window.show()

    logger.info("Application window shown. Ready for scanning.")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
