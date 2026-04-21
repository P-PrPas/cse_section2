"""
Face detection and verification module using OpenCV DNN.
Uses YuNet for face detection and SFace for face recognition/verification.
These are lightweight ONNX models bundled with the application (~40MB total).
No TensorFlow, dlib, or external API dependencies.
"""

import logging
import os
import shutil
import tempfile
import threading
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Default model paths (relative to project root)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DETECTOR_PATH = os.path.join(
    _BASE_DIR, "models", "face_detection_yunet_2023mar.onnx"
)
DEFAULT_RECOGNIZER_PATH = os.path.join(
    _BASE_DIR, "models", "face_recognition_sface_2021dec.onnx"
)


def _ensure_ascii_path(original_path: str) -> str:
    """
    OpenCV DNN cannot read files from paths containing non-ASCII characters
    (e.g., Thai, Chinese). If the path has non-ASCII chars, copy the file
    to a temp directory with an ASCII-only path.
    
    Returns a path safe for OpenCV DNN to read.
    """
    try:
        original_path.encode('ascii')
        return original_path  # Already ASCII-safe
    except UnicodeEncodeError:
        pass

    # Copy to temp dir with ASCII path
    basename = os.path.basename(original_path)
    # Ensure basename is also ASCII
    try:
        basename.encode('ascii')
    except UnicodeEncodeError:
        basename = "model.onnx"

    temp_dir = os.path.join(tempfile.gettempdir(), "edfvs_models")
    os.makedirs(temp_dir, exist_ok=True)
    safe_path = os.path.join(temp_dir, basename)

    if not os.path.exists(safe_path) or \
       os.path.getsize(safe_path) != os.path.getsize(original_path):
        logger.info(
            "Copying model to ASCII-safe path: %s -> %s",
            original_path, safe_path
        )
        shutil.copy2(original_path, safe_path)

    return safe_path


class FaceVerifier:
    """
    Face detection + verification engine using OpenCV's DNN modules.
    
    - Detection: cv2.FaceDetectorYN (YuNet model)
    - Recognition: cv2.FaceRecognizerSF (SFace model)
    
    Both use small ONNX files, no heavy frameworks needed.
    """

    def __init__(self, detector_path: str = None,
                 recognizer_path: str = None,
                 score_threshold: float = 0.7,
                 nms_threshold: float = 0.3):
        """
        Initialize the face verifier with model paths.
        
        Args:
            detector_path: Path to YuNet ONNX model.
            recognizer_path: Path to SFace ONNX model.
            score_threshold: Minimum confidence for face detection.
            nms_threshold: NMS threshold for overlapping detections.
        """
        self.lock = threading.Lock()
        self._detector = None
        self._detector_size = (0, 0)
        
        self._detector_path_orig = detector_path or DEFAULT_DETECTOR_PATH
        self._recognizer_path_orig = recognizer_path or DEFAULT_RECOGNIZER_PATH
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold

        # Validate model files exist
        if not os.path.exists(self._detector_path_orig):
            raise FileNotFoundError(
                f"Face detector model not found: {self._detector_path_orig}"
            )
        if not os.path.exists(self._recognizer_path_orig):
            raise FileNotFoundError(
                f"Face recognizer model not found: {self._recognizer_path_orig}"
            )

        # Ensure paths are ASCII-safe for OpenCV DNN
        self.detector_path = _ensure_ascii_path(self._detector_path_orig)
        self.recognizer_path = _ensure_ascii_path(self._recognizer_path_orig)

        # Initialize recognizer
        self.recognizer = cv2.FaceRecognizerSF.create(
            self.recognizer_path, ""
        )
        logger.info("FaceVerifier initialized with YuNet + SFace.")

    def _get_detector(self, image_width: int, image_height: int):
        """Get or create a YuNet detector sized for the given image dimensions."""
        if self._detector is None:
            self._detector = cv2.FaceDetectorYN.create(
                self.detector_path,
                "",
                (image_width, image_height),
                self.score_threshold,
                self.nms_threshold
            )
            self._detector_size = (image_width, image_height)
        elif self._detector_size != (image_width, image_height):
            self._detector.setInputSize((image_width, image_height))
            self._detector_size = (image_width, image_height)
        return self._detector

    def detect_faces(self, image: np.ndarray) -> np.ndarray:
        """
        Detect faces in an image.
        
        Args:
            image: BGR image as numpy array.
        
        Returns:
            Array of detected faces. Each row contains:
            [x, y, w, h, ...landmarks..., score]
            Returns None if no faces detected.
        """
        if image is None or image.size == 0:
            return None

        h, w = image.shape[:2]
        with self.lock:
            detector = self._get_detector(w, h)
            _, faces = detector.detect(image)

        return faces

    def get_largest_face(self, faces: np.ndarray) -> np.ndarray:
        """
        Select the face with the largest bounding box area.
        
        Args:
            faces: Array of detected faces from detect_faces().
        
        Returns:
            Single face row (1D array).
        """
        if faces is None or len(faces) == 0:
            return None

        # Compute area (w * h) for each face
        areas = faces[:, 2] * faces[:, 3]
        largest_idx = np.argmax(areas)

        # Skip logging at 30fps to avoid console spam during real-time tracking
        # logger.info(
        #     "Selected largest face: idx=%d, area=%.0f (out of %d faces)",
        #     largest_idx, areas[largest_idx], len(faces)
        # )

        return faces[largest_idx]

    def extract_embedding(self, image: np.ndarray,
                          face: np.ndarray) -> np.ndarray:
        """
        Extract a face embedding (feature vector) for recognition.
        
        Args:
            image: Original BGR image.
            face: Single face detection result from detect_faces().
        
        Returns:
            128-dim feature vector.
        """
        with self.lock:
            aligned = self.recognizer.alignCrop(image, face)
            embedding = self.recognizer.feature(aligned)
        return embedding

    def draw_debug_faces(self, image: np.ndarray, faces: np.ndarray, color=(248, 189, 56)) -> np.ndarray:
        """
        Draw a modern reticle bounding box for detected faces.
        """
        debug_img = image.copy()
        if faces is None or len(faces) == 0:
            return debug_img

        for face in faces:
            # Face components: x, y, w, h
            box = list(map(int, face[:4]))
            x, y, w, h = box[0], box[1], box[2], box[3]
            
            # Corner line length
            cl = int(min(w, h) * 0.2)
            th = 2 # thickness
            
            # Top-left
            cv2.line(debug_img, (x, y), (x+cl, y), color, th)
            cv2.line(debug_img, (x, y), (x, y+cl), color, th)
            # Top-right
            cv2.line(debug_img, (x+w, y), (x+w-cl, y), color, th)
            cv2.line(debug_img, (x+w, y), (x+w, y+cl), color, th)
            # Bottom-left
            cv2.line(debug_img, (x, y+h), (x+cl, y+h), color, th)
            cv2.line(debug_img, (x, y+h), (x, y-cl+h), color, th)
            # Bottom-right
            cv2.line(debug_img, (x+w, y+h), (x+w-cl, y+h), color, th)
            cv2.line(debug_img, (x+w, y+h), (x+w, y-cl+h), color, th)

        return debug_img

    def _resize_image(self, image: np.ndarray, max_size: int = 1024) -> np.ndarray:
        """
        Resize an image so its longest edge does not exceed max_size,
        maintaining aspect ratio. Prevents memory allocation errors in YuNet.
        """
        if image is None or image.size == 0:
            return image
            
        h, w = image.shape[:2]
        if max(h, w) <= max_size:
            return image
            
        scale = max_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def verify(self, img_digital: np.ndarray, img_webcam: np.ndarray, img_local: np.ndarray = None,
               threshold: float = 0.40) -> dict:
        """
        Verify whether images contain the same person's face.
        
        Detects faces in all images, extracts embeddings, and computes
        cosine similarity. Input images are automatically resized if they
        exceed 1024px to prevent memory allocation errors.
        
        Args:
            img_digital: BGR image of the digital original document.
            img_webcam: BGR image captured from webcam.
            img_local: (Optional) BGR image of the local file database.
            threshold: Cosine similarity threshold. Higher = stricter.
                       Score >= threshold means MATCH.
        
        Returns:
            Dict with:
                - 'verified': bool
                - 'score': float (overall score or webcam score)
                - 'score_webcam': float
                - 'score_local': float (None if not provided)
                - 'threshold': float
                - 'error': str (if face detection failed)
                - 'img_digital_debug': np.ndarray
                - 'img_webcam_debug': np.ndarray
                - 'img_local_debug': np.ndarray (None if not provided)
        """
        # Resize images to prevent bad allocation errors in YuNet
        img_digital = self._resize_image(img_digital)
        img_webcam = self._resize_image(img_webcam)
        if img_local is not None:
            img_local = self._resize_image(img_local)

        # Detect faces in digital original
        faces_digital = self.detect_faces(img_digital)
        img_digital_debug = self.draw_debug_faces(img_digital, faces_digital, color=(255, 0, 0)) # Blue for digital
        if faces_digital is None or len(faces_digital) == 0:
            return {
                "verified": False,
                "score": 0.0,
                "score_webcam": 0.0,
                "score_local": None,
                "threshold": threshold,
                "error": "ไม่พบใบหน้าในเอกสารต้นฉบับ\nNo face detected in the digital original document.",
                "img_digital_debug": img_digital_debug,
                "img_webcam_debug": img_webcam.copy(),
                "img_local_debug": img_local.copy() if img_local is not None else None
            }

        # Detect faces in webcam frame
        faces_webcam = self.detect_faces(img_webcam)
        # Select largest
        face_webcam = self.get_largest_face(faces_webcam)
        # Draw all found faces, highlight largest
        img_webcam_debug = self.draw_debug_faces(img_webcam, faces_webcam, color=(0, 255, 255)) # Yellow for all
        if face_webcam is not None:
             img_webcam_debug = self.draw_debug_faces(img_webcam_debug, np.array([face_webcam]), color=(0, 255, 0)) # Green for largest

        if faces_webcam is None or len(faces_webcam) == 0:
            return {
                "verified": False,
                "score": 0.0,
                "score_webcam": 0.0,
                "score_local": None,
                "threshold": threshold,
                "error": "ไม่พบใบหน้าบนกล้อง กรุณาจัดตำแหน่งใหม่\nNo face detected on camera. Please adjust position.",
                "img_digital_debug": img_digital_debug,
                "img_webcam_debug": img_webcam_debug,
                "img_local_debug": img_local.copy() if img_local is not None else None
            }

        img_local_debug = None
        face_local = None
        if img_local is not None:
            faces_local = self.detect_faces(img_local)
            face_local = self.get_largest_face(faces_local)
            img_local_debug = self.draw_debug_faces(img_local, faces_local, color=(0, 255, 255)) # Yellow
            if face_local is not None:
                 img_local_debug = self.draw_debug_faces(img_local_debug, np.array([face_local]), color=(0, 255, 0)) # Green
        
        # Take first face from digital, largest from webcam, largest from local
        face_digital = faces_digital[0]

        # Extract embeddings
        emb_digital = self.extract_embedding(img_digital, face_digital)
        emb_webcam = self.extract_embedding(img_webcam, face_webcam)
        
        emb_local = None
        if face_local is not None:
            emb_local = self.extract_embedding(img_local, face_local)

        # Compute cosine similarity
        with self.lock:
            score_webcam = self.recognizer.match(
                emb_digital, emb_webcam,
                cv2.FaceRecognizerSF_FR_COSINE
            )
            score_local = None
            if emb_local is not None:
                score_local = self.recognizer.match(
                    emb_digital, emb_local,
                    cv2.FaceRecognizerSF_FR_COSINE
                )

        is_match_webcam = score_webcam >= threshold
        # Overall verification is True if webcam is matched (basic) - the caller will do advanced logic
        is_match = is_match_webcam

        logger.info(
            "Verification: score_webcam=%.4f, score_local=%s, threshold=%.4f",
            score_webcam, f"{score_local:.4f}" if score_local is not None else "None", threshold
        )

        return {
            "verified": is_match,
            "score": round(float(score_webcam), 4),
            "score_webcam": round(float(score_webcam), 4),
            "score_local": round(float(score_local), 4) if score_local is not None else None,
            "threshold": threshold,
            "img_digital_debug": img_digital_debug,
            "img_webcam_debug": img_webcam_debug,
            "img_local_debug": img_local_debug
        }
