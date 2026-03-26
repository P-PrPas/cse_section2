"""
Scanner input listener module.
Listens for USB QR scanner input (keyboard emulator mode) on a background
thread and emits the scanned URL string as a Qt signal when Enter is pressed.
"""

import logging
import re
from PyQt5.QtCore import QThread, pyqtSignal
from pynput import keyboard

logger = logging.getLogger(__name__)


class ScannerListenerThread(QThread):
    """
    Background thread that captures keyboard input from a USB QR scanner.
    
    USB barcode/QR scanners typically emulate a keyboard: they type the
    decoded string character by character and then press Enter.
    
    This thread buffers incoming keystrokes and emits the full string
    via the `code_scanned` signal when Enter is detected.
    
    Signals:
        code_scanned(str): Emitted with the full scanned string.
    """

    code_scanned = pyqtSignal(str)

    def __init__(self, url_pattern: str = r"^\d{13}$", parent=None):
        super().__init__(parent)
        self._buffer = []
        self._url_pattern = url_pattern
        self._listener = None
        self._running = True

    def run(self):
        """Start the keyboard listener (blocking until stopped)."""
        logger.info("Scanner listener started.")

        def on_press(key):
            if not self._running:
                return False  # Stop listener

            try:
                if key == keyboard.Key.enter:
                    self._process_buffer()
                elif key == keyboard.Key.space:
                    self._buffer.append(' ')
                elif hasattr(key, 'char') and key.char is not None:
                    self._buffer.append(key.char)
            except Exception as e:
                logger.error("Error in scanner listener: %s", str(e))

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()
        self._listener.join()

    def _process_buffer(self):
        """Process the accumulated keystroke buffer."""
        if not self._buffer:
            return

        scanned_text = ''.join(self._buffer).strip()
        self._buffer.clear()

        if len(scanned_text) < 5:
            logger.debug("Ignoring short input: '%s'", scanned_text)
            return

        if re.match(self._url_pattern, scanned_text):
            logger.info("Valid National ID scanned: %s", scanned_text)
            self.code_scanned.emit(scanned_text)
        else:
            logger.warning("Scanned data is not a valid National ID: '%s'", scanned_text)

    def stop(self):
        """Stop the scanner listener thread."""
        self._running = False
        if self._listener:
            self._listener.stop()
        logger.info("Scanner listener stopped.")
