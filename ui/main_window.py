"""
Main GUI window for EDFVS.
Displays real-time webcam feed, handles scanner input, runs the
face verification pipeline, and shows clear pass/fail/error indicators.
"""

import logging
import time
import traceback

import cv2
import numpy as np
from PyQt5.QtCore import (Qt, QTimer, QThread, pyqtSignal, pyqtSlot)
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFrame, QGraphicsDropShadowEffect, QStackedWidget, QComboBox, QPushButton
)
from PyQt5.QtMultimedia import QCameraInfo

from modules.face_verifier import FaceVerifier
from modules.ocsc_scraper import OcscScraperThread, ScraperStatus
from modules.image_enhance import apply_clahe
from modules.scanner_listener import ScannerListenerThread
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)

def add_shadow(widget, blur=25, offset=8, alpha=100):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setColor(QColor(0, 0, 0, alpha))
    shadow.setOffset(0, offset)
    widget.setGraphicsEffect(shadow)

class VerificationWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, digital_img: np.ndarray, webcam_frame: np.ndarray, config: dict,
                 face_verifier: FaceVerifier, parent=None):
        super().__init__(parent)
        self.digital_img = digital_img
        self.webcam_frame = webcam_frame.copy()
        self.config = config
        self.face_verifier = face_verifier

    def run(self):
        try:
            start = time.time()
            if self.digital_img is None:
                raise ValueError("No digital image provided.")
                
            enhanced_frame = apply_clahe(
                self.webcam_frame,
                clip_limit=self.config.get("clahe_clip_limit", 2.0),
                grid_size=tuple(self.config.get("clahe_grid_size", [8, 8]))
            )
            
            enhanced_digital = apply_clahe(
                self.digital_img,
                clip_limit=self.config.get("clahe_clip_limit", 2.0),
                grid_size=tuple(self.config.get("clahe_grid_size", [8, 8]))
            )

            threshold = self.config.get("match_threshold", 0.35)
            result = self.face_verifier.verify(
                enhanced_digital, enhanced_frame, threshold=threshold
            )

            elapsed = time.time() - start
            result["elapsed"] = round(elapsed, 2)
            result["digital_image"] = result.get("img_digital_debug", enhanced_digital)
            result["webcam_image"] = result.get("img_webcam_debug", enhanced_frame)
            self.finished.emit(result)

        except Exception as e:
            logger.error("Unexpected error: %s\n%s", str(e), traceback.format_exc())
            self.error.emit(f"Unexpected error:\n{str(e)}")


class MainWindow(QMainWindow):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.cap = None
        self.scanner_thread = None
        self.scraper_thread = None
        self.worker = None
        self._processing = False
        self._current_frame = None
        self._reticle_color = (248, 189, 56) # Sky Blue BGR Default
        self.camera_timer = None
        self._camera_rotation_deg = 0
        self._last_sound_at = 0.0

        self.setWindowTitle("EDFVS — Premium Edition")
        self.setMinimumSize(1200, 800)

        try:
            self.face_verifier = FaceVerifier()
            logger.info("FaceVerifier initialized successfully.")
        except FileNotFoundError as e:
            logger.error("Model files missing: %s", e)
            self.face_verifier = None

        self._init_ui()
        self._init_camera()
        self._init_scraper()
        self._init_scanner()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            QMainWindow { background-color: #0F172A; }
            QLabel { font-family: 'Segoe UI', sans-serif; }
            QWidget#Card { background-color: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; }
            QWidget#CardHeader { background-color: rgba(30, 41, 59, 0.5); border-bottom: 1px solid rgba(255,255,255,0.05); border-top-left-radius: 16px; border-top-right-radius: 16px; }
        """)

        # ── 1. Header ──
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet("background-color: #0F172A; border-bottom: 1px solid #1E293B;")
        add_shadow(header, 15, 4, 50)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(30, 0, 30, 0)

        h_left = QHBoxLayout()
        shield_icon = QLabel("🛡️")
        shield_icon.setFont(QFont("Segoe UI", 24))
        h_left.addWidget(shield_icon)
        
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.setAlignment(Qt.AlignVCenter)
        title = QLabel("EDFVS")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: white; border: none; letter-spacing: 1px;")
        subtitle = QLabel("EXAM DOCUMENT FACE VERIFICATION SYSTEM")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: #94A3B8; border: none; letter-spacing: 1px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        h_left.addLayout(title_box)
        h_layout.addLayout(h_left)
        h_layout.addStretch()

        h_right = QHBoxLayout()
        h_right.setSpacing(20)
        online_dot = QLabel("🟢 System Online")
        online_dot.setStyleSheet("color: #94A3B8; font-size: 13px; border: none;")
        terminal = QLabel("Terminal ID: REG-001")
        terminal.setStyleSheet("color: #94A3B8; font-size: 13px; border-left: 1px solid #334155; padding-left: 15px;")
        h_right.addWidget(online_dot)
        h_right.addWidget(terminal)
        h_layout.addLayout(h_right)
        main_layout.addWidget(header)

        # ── 2. Main Content Cards ──
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(30)

        # Left / Camera Card
        self.cam_card = QWidget()
        self.cam_card.setObjectName("Card")
        cam_layout = QVBoxLayout(self.cam_card)
        cam_layout.setContentsMargins(0, 0, 0, 0)
        cam_layout.setSpacing(0)
        
        cam_header = QWidget()
        cam_header.setObjectName("CardHeader")
        cam_header.setFixedHeight(55)
        ch_layout = QHBoxLayout(cam_header)
        ch_layout.setContentsMargins(20, 0, 20, 0)
        ch_title = QLabel("📷 Live Camera")
        ch_title.setStyleSheet("color: #E2E8F0; font-weight: bold; font-size: 14px; border: none;")
        ch_layout.addWidget(ch_title)
        ch_layout.addStretch()

        self.rotate_cam_btn = QPushButton("⟳ Rotate")
        self.rotate_cam_btn.setCursor(Qt.PointingHandCursor)
        self.rotate_cam_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #E2E8F0;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 4px 10px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
            QPushButton:hover { background-color: #3b4b63; }
            QPushButton:pressed { background-color: #1f2a3a; }
        """)
        self.rotate_cam_btn.clicked.connect(self._rotate_camera)
        ch_layout.addWidget(self.rotate_cam_btn)

        self.camera_combo = QComboBox()
        self.camera_combo.setStyleSheet("""
            QComboBox {
                background-color: #334155;
                color: #E2E8F0;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 4px 10px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E293B;
                color: #E2E8F0;
                selection-background-color: #3B82F6;
                outline: none;
            }
        """)
        ch_layout.addWidget(self.camera_combo)
        cam_layout.addWidget(cam_header)

        self.webcam_label = QLabel()
        self.webcam_label.setAlignment(Qt.AlignCenter)
        self.webcam_label.setStyleSheet("background-color: #000000; border-bottom-left-radius: 16px; border-bottom-right-radius: 16px;")
        cam_layout.addWidget(self.webcam_label, 1)
        add_shadow(self.cam_card, 40, 15, 60)
        content_layout.addWidget(self.cam_card, 1)

        # Right / Digital Source Card
        self.doc_card = QWidget()
        self.doc_card.setObjectName("Card")
        doc_layout = QVBoxLayout(self.doc_card)
        doc_layout.setContentsMargins(0, 0, 0, 0)
        doc_layout.setSpacing(0)

        doc_header = QWidget()
        doc_header.setObjectName("CardHeader")
        doc_header.setFixedHeight(55)
        dh_layout = QHBoxLayout(doc_header)
        dh_layout.setContentsMargins(20, 0, 20, 0)
        dh_title = QLabel("📄 Digital Source")
        dh_title.setStyleSheet("color: #E2E8F0; font-weight: bold; font-size: 14px; border: none;")
        dh_badge = QLabel("from QR Code")
        dh_badge.setStyleSheet("color: #94A3B8; background-color: #334155; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 11px; border: none;")
        dh_layout.addWidget(dh_title)
        dh_layout.addStretch()
        dh_layout.addWidget(dh_badge)
        doc_layout.addWidget(doc_header)

        self.doc_stack = QStackedWidget()
        
        # Idle State
        idle_widget = QWidget()
        idle_layout = QVBoxLayout(idle_widget)
        idle_layout.setAlignment(Qt.AlignCenter)
        idle_icon = QLabel("🔲")
        idle_icon.setFont(QFont("Segoe UI", 48))
        idle_icon.setAlignment(Qt.AlignCenter)
        idle_icon.setStyleSheet("color: #475569; background: transparent; border: none;")
        idle_text = QLabel("Waiting for Document Scan")
        idle_text.setFont(QFont("Segoe UI", 16))
        idle_text.setStyleSheet("color: #94A3B8; background: transparent; border: none;")
        idle_text.setAlignment(Qt.AlignCenter)
        idle_sub = QLabel("Scan the QR code on the physical document\nto fetch data.")
        idle_sub.setStyleSheet("color: #64748B; font-size: 13px; background: transparent; border: none;")
        idle_sub.setAlignment(Qt.AlignCenter)
        idle_layout.addWidget(idle_icon)
        idle_layout.addWidget(idle_text)
        idle_layout.addWidget(idle_sub)

        # Loading State
        loading_widget = QWidget()
        loading_layout = QVBoxLayout(loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        load_icon = QLabel("⏳")
        load_icon.setFont(QFont("Segoe UI", 48))
        load_icon.setAlignment(Qt.AlignCenter)
        load_icon.setStyleSheet("background: transparent; border: none;")
        load_text = QLabel("Fetching Original Document...")
        load_text.setFont(QFont("Segoe UI", 16))
        load_text.setStyleSheet("color: #38BDF8; background: transparent; border: none;")
        load_text.setAlignment(Qt.AlignCenter)
        loading_layout.addWidget(load_icon)
        loading_layout.addWidget(load_text)

        # Loaded State
        self.digital_label = QLabel()
        self.digital_label.setAlignment(Qt.AlignCenter)
        self.digital_label.setStyleSheet("background-color: #0F172A; border-bottom-left-radius: 16px; border-bottom-right-radius: 16px;")

        self.doc_stack.addWidget(idle_widget)
        self.doc_stack.addWidget(loading_widget)
        self.doc_stack.addWidget(self.digital_label)
        self.doc_stack.setStyleSheet("background: transparent; border: none;")
        
        doc_layout.addWidget(self.doc_stack, 1)
        add_shadow(self.doc_card, 40, 15, 60)
        content_layout.addWidget(self.doc_card, 1)
        main_layout.addWidget(content_widget, 1)

        # ── 3. Bottom Status Bar ──
        self.status_panel = QWidget()
        self.status_panel.setFixedHeight(120)
        self.status_panel.setStyleSheet("background-color: #1E293B; border-top: 1px solid #334155;")
        sp_layout = QHBoxLayout(self.status_panel)
        sp_layout.setContentsMargins(40, 0, 40, 0)
        sp_layout.setSpacing(25)

        self.status_icon = QLabel("🔍")
        self.status_icon.setFixedSize(65, 65)
        self.status_icon.setAlignment(Qt.AlignCenter)
        self.status_icon.setFont(QFont("Segoe UI", 26))
        
        status_text_box = QVBoxLayout()
        status_text_box.setAlignment(Qt.AlignVCenter)
        self.status_title = QLabel("READY TO SCAN")
        self.status_title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self.status_desc = QLabel("Please scan the QR code to begin verification.")
        self.status_desc.setFont(QFont("Segoe UI", 13))
        status_text_box.addWidget(self.status_title)
        status_text_box.addWidget(self.status_desc)

        sp_layout.addWidget(self.status_icon)
        sp_layout.addLayout(status_text_box)
        sp_layout.addStretch()

        self.score_box = QVBoxLayout()
        self.score_box.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        score_lbl = QLabel("CONFIDENCE SCORE")
        score_lbl.setStyleSheet("color: #94A3B8; font-family: monospace; font-size: 12px; border: none; background: transparent;")
        score_lbl.setAlignment(Qt.AlignRight)
        self.score_val = QLabel("--%")
        self.score_val.setFont(QFont("Segoe UI", 28, QFont.Bold))
        self.score_val.setStyleSheet("color: white; border: none; background: transparent;")
        self.score_val.setAlignment(Qt.AlignRight)
        self.score_box.addWidget(score_lbl)
        self.score_box.addWidget(self.score_val)
        
        self.score_container = QWidget()
        self.score_container.setStyleSheet("background: transparent; border: none;")
        self.score_container.setLayout(self.score_box)
        self.score_container.hide()
        sp_layout.addWidget(self.score_container)

        main_layout.addWidget(self.status_panel)
        self._reset_to_standby()

    def _init_camera(self):
        # Populate available cameras using QCameraInfo
        self.available_cameras = QCameraInfo.availableCameras()
        self.camera_combo.clear()
        
        if not self.available_cameras:
            self.camera_combo.addItem("No Camera Found")
            self.camera_combo.setEnabled(False)
            logger.error("No camera hardware found on this system.")
        else:
            for cam in self.available_cameras:
                self.camera_combo.addItem(cam.description())
                
            # Default to config or index 0
            cam_index = self.config.get("camera_index", 0)
            if cam_index < len(self.available_cameras):
                self.camera_combo.setCurrentIndex(cam_index)
            else:
                cam_index = 0
            
            self.camera_combo.currentIndexChanged.connect(self._change_camera)
            # Boot first camera
            self._start_capture(cam_index)

    def _change_camera(self, index):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            time.sleep(0.1) # Small delay to free hardware
            
        self.config["camera_index"] = index # Save to current session config
        self._start_capture(index)
        
    def _start_capture(self, index):
        if hasattr(self, 'camera_timer') and self.camera_timer and self.camera_timer.isActive():
            self.camera_timer.stop()

        # cv2.VideoCapture uses numeric indexing sequentially in Windows DirectShow
        # Using cv2.CAP_DSHOW provides much faster intialization natively on windows
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            logger.error("Failed to open camera at index %d", index)
            # Try without DSHOW fallback 
            self.cap = cv2.VideoCapture(index)

        if self.cap.isOpened():
            logger.info("Camera %d opened successfully.", index)
            self.camera_timer = QTimer(self)
            self.camera_timer.timeout.connect(self._update_frame)
            self.camera_timer.start(33)
        else:
            logger.error("Camera %d failed again.", index)

    def _update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            return

        rotated = self._apply_camera_rotation(frame)
        self._current_frame = rotated.copy()
        display_frame = rotated.copy()
        
        if self.face_verifier is not None:
            try:
                faces = self.face_verifier.detect_faces(display_frame)
                if faces is not None and len(faces) > 0:
                    display_frame = self.face_verifier.draw_debug_faces(display_frame, faces, color=self._reticle_color)
            except Exception as e:
                logger.error("Face detection error: %s", str(e))

        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self.webcam_label.width(), self.webcam_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.webcam_label.setPixmap(pixmap)

    def _apply_camera_rotation(self, frame: np.ndarray) -> np.ndarray:
        if frame is None:
            return frame
        deg = int(self._camera_rotation_deg) % 360
        if deg == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        if deg == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        if deg == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def _rotate_camera(self):
        self._camera_rotation_deg = (int(self._camera_rotation_deg) + 90) % 360
        logger.info("Camera rotation set to %d degrees.", self._camera_rotation_deg)

    def _init_scraper(self):
        load_dotenv()
        user = os.environ.get("OCSC_USER", "eexamphoto")
        pwd = os.environ.get("OCSC_PASSWORD", "zLc3R/IZNfapHG5Idk2T3A==")
        self.scraper_thread = OcscScraperThread(user, pwd, parent=self)
        self.scraper_thread.status_changed.connect(self._on_scraper_status_changed)
        self.scraper_thread.search_finished.connect(self._on_scraper_finished)
        self.scraper_thread.start()

    @pyqtSlot(str, str)
    def _on_scraper_status_changed(self, status: str, msg: str):
        if status in [ScraperStatus.STARTING, ScraperStatus.LOGGING_IN]:
            self.doc_stack.setCurrentIndex(1)
            self._set_status(
                "SYSTEM INIT", msg, "⚙️",
                "background-color: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 16px;",
                "background-color: #0F172A; border-top: 1px solid #1E293B;",
                "#38BDF8"
            )
        elif status == ScraperStatus.READY:
            if not self._processing:
                self._reset_to_standby()
        elif status == ScraperStatus.FATAL:
            self._show_error(f"Scraper Fatal Error: {msg}")

    def _init_scanner(self):
        url_pattern = self.config.get("url_pattern", r"^\d{13}$")
        self.scanner_thread = ScannerListenerThread(url_pattern=url_pattern, parent=self)
        self.scanner_thread.code_scanned.connect(self._on_code_scanned)
        self.scanner_thread.start()

    @pyqtSlot(str)
    def _on_code_scanned(self, national_id: str):
        if self._processing: return
        if self.face_verifier is None:
            self._show_error("AI model not ready. Please check model files.")
            return
        if self.scraper_thread is None or not self.scraper_thread.isRunning():
            self._show_error("Web Scraper is not running.")
            return

        self._processing = True
        logger.info("National ID scanned: %s", national_id)

        self.doc_stack.setCurrentIndex(1)
        self._set_status(
            "FETCHING DATA...", f"Searching OCSC for ID: {national_id}", "⏳",
            "background-color: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 16px;",
            "background-color: #0F172A; border-top: 1px solid #1E293B;",
            "#38BDF8"
        )
        self._reticle_color = (248, 189, 56) # Sky Blue processing

        if self._current_frame is None:
            self._show_error("Camera frame not available. Check connection.")
            return

        # Queue the search to playwright
        self.scraper_thread.enqueue_search(national_id)

    @pyqtSlot(str, object, str)
    def _on_scraper_finished(self, nat_id: str, img: np.ndarray, err: str):
        if err or img is None:
            self._show_error(err or "Failed to retrieve image form OCSC.")
            return

        self._set_status(
            "VERIFYING...", "Analyzing facial geometry against OCSC photo...", "🔍",
            "background-color: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 16px;",
            "background-color: #0F172A; border-top: 1px solid #1E293B;",
            "#10B981"
        )

        self.worker = VerificationWorker(img, self._current_frame, self.config, self.face_verifier, self)
        self.worker.finished.connect(self._on_verification_done)
        self.worker.error.connect(self._show_error)
        self.worker.start()

    @pyqtSlot(dict)
    def _on_verification_done(self, result: dict):
        error_msg = result.get("error")
        is_match = result.get("verified", False)
        score = result.get("score", 0)
        elapsed = result.get("elapsed", 0)
        digital_image = result.get("digital_image")
        threshold = self.config.get("match_threshold", 0.35)

        if score >= threshold:
            pct = 85.0 + ((score - threshold) / (1.0 - threshold)) * 15.0
        else:
            pct = max(0.0, ((score + 0.2) / (threshold + 0.2)) * 84.0)
        pct = min(100.0, max(0.0, pct))
        self.score_val.setText(f"{pct:.1f}%")
        self.score_container.show()

        if digital_image is not None:
            self._display_image(self.digital_label, digital_image)
            self.doc_stack.setCurrentIndex(2)

        if error_msg:
            self._play_feedback_sound("alert")
            self._reticle_color = (68, 68, 239) # Red
            self._set_status(
                "ERROR", str(error_msg), "⚠️",
                "background-color: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 16px;",
                "background-color: #450A0A; border-top: 1px solid #7F1D1D;",
                "#F87171"
            )
            self.score_val.setStyleSheet("color: #F87171; background: transparent; border: none;")
        elif is_match:
            if pct < 80.0:
                self._play_feedback_sound("warning")
            self._reticle_color = (129, 185, 16) # Emerald
            self._set_status(
                "MATCH VERIFIED", "Identity confirmed. Proceed to examination room.", "✅",
                "background-color: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 16px;",
                "background-color: #022C22; border-top: 1px solid #064E3B;",
                "#34D399"
            )
            self.score_val.setStyleSheet("color: #34D399; background: transparent; border: none;")
        else:
            self._play_feedback_sound("alert")
            self._reticle_color = (68, 68, 239) # Red
            self._set_status(
                "MISMATCH ALERT", "Identity cannot be verified. Please contact supervisor.", "❌",
                "background-color: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 16px;",
                "background-color: #450A0A; border-top: 1px solid #7F1D1D;",
                "#F87171"
            )
            self.score_val.setStyleSheet("color: #F87171; background: transparent; border: none;")

        reset_delay = self.config.get("auto_reset_delay", 3)
        QTimer.singleShot(int(reset_delay * 1000), self._reset_to_standby)

    @pyqtSlot(str)
    def _show_error(self, message: str):
        self._play_feedback_sound("alert")
        self._reticle_color = (68, 68, 239)
        self._set_status(
            "ERROR", str(message), "⚠️",
            "background-color: rgba(249, 115, 22, 0.15); border: 1px solid rgba(249, 115, 22, 0.3); border-radius: 16px;",
            "background-color: #431407; border-top: 1px solid #7C2D12;",
            "#FB923C"
        )
        reset_delay = self.config.get("auto_reset_delay", 3)
        QTimer.singleShot(int(reset_delay * 1000), self._reset_to_standby)

    def _play_feedback_sound(self, kind: str):
        """
        kind:
          - 'warning': score < 80% but still MATCH
          - 'alert': mismatch / below threshold / error
        """
        now = time.time()
        min_gap = float(self.config.get("sound_min_gap_sec", 0.75))
        if now - float(self._last_sound_at) < min_gap:
            return
        self._last_sound_at = now

        try:
            import winsound
        except Exception:
            return

        try:
            if kind == "warning":
                # Gentle double-beep
                winsound.Beep(880, 90)
                winsound.Beep(880, 90)
            else:
                # Clear alert
                winsound.MessageBeep(winsound.MB_ICONHAND)
                winsound.Beep(1200, 140)
                winsound.Beep(900, 160)
        except Exception:
            # Never let sound failures break the verification flow
            return

    def _reset_to_standby(self):
        self._processing = False
        self._reticle_color = (248, 189, 56) # Sky Blue BGR
        self.doc_stack.setCurrentIndex(0)
        self.score_container.hide()
        self._set_status(
            "READY TO SCAN", "Please scan the QR code to begin verification.", "🔍",
            "background-color: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 16px;",
            "background-color: #1E293B; border-top: 1px solid #334155;",
            "white"
        )

    def _set_status(self, title: str, desc: str, icon: str, icon_style: str, panel_style: str, title_color: str):
        self.status_title.setText(title)
        self.status_title.setStyleSheet(f"color: {title_color}; border: none; background: transparent; letter-spacing: 1px;")
        self.status_desc.setText(desc)
        self.status_desc.setStyleSheet("color: #94A3B8; border: none; background: transparent;")
        self.status_icon.setText(icon)
        self.status_icon.setStyleSheet(icon_style)
        self.status_panel.setStyleSheet(panel_style)

    def _display_image(self, label: QLabel, image: np.ndarray):
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self.digital_label.width(), self.digital_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        label.setPixmap(pixmap)

    def closeEvent(self, event):
        logger.info("Shutting down EDFVS...")
        if hasattr(self, 'camera_timer') and self.camera_timer and self.camera_timer.isActive():
            self.camera_timer.stop()
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if self.scanner_thread:
            self.scanner_thread.stop()
            self.scanner_thread.wait(2000)
        if self.scraper_thread:
            self.scraper_thread.stop()
            self.scraper_thread.wait(3000)
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(1000)
        event.accept()
