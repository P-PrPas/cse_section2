# EDFVS: Exam Document Face Verification System

**EDFVS (Premium Edition)** is an offline-first, highly reliable Face Verification System designed for enterprise-level exam proctoring and identity verification (e.g., OCSC examinations). 

The system utilizes high-performance Computer Vision to perform a robust **Tri-Source Verification**, comparing a candidate's identity across the Live Webcam feed, a Web Portal (via QR Code scanning), and a Local Digital Database, all without relying on cloud-based AI inference.

---

## ✨ Features

- **🛡️ Tri-Source Face Verification**: Enhances security by comparing faces from three distinct sources side-by-side:
  1. **Web Source**: Automates data retrieval by scanning a QR Code, securely logging into the registration portal using an integrated Playwright scraper.
  2. **Live Camera**: Captures the candidate's face in real-time.
  3. **Local Database**: Validates against pre-existing local image records for additional confidence.
- **⚡ Offline-First AI Engine**: All facial recognition processes run entirely locally, ensuring zero data leakage and maintaining strict privacy compliance (Privacy-first).
- **🎭 Real-Time Face Detection & Recognition**: Optimized OpenCV DNN architecture utilizing lightweight, state-of-the-art models:
  - *YuNet (2023)* for sub-millisecond face detection.
  - *SFace (2021)* for high-accuracy facial feature extraction and cosine similarity comparison.
- **🎨 Premium Dark UI**: The user interface is completely reimagined in a "Modern Slate / Tailwind-inspired" aesthetic utilizing PyQt5. It features sleek status indicators, modern bounding box reticles, and intuitive split-pane dashboard layouts, significantly reducing proctor fatigue.
- **🔊 Smart Audio Feedback & Dual-Scoring**: Includes granular logic to handle partial matches across different sources, outputting specific visual alerts and audio cues (e.g., gentle double-beeps for low-confidence matches, sharp alerts for mismatches and errors).
- **⚙️ Dynamic Configuration**: Administrators can easily adjust strictness thresholds, camera configurations, hardware thread limits (to prevent OpenBLAS memory allocation issues), and lighting enhancement (CLAHE) settings via a simple `config.json` file.

---

## 🏗️ Directory Structure

```text
CSE_Section2/
├── assets/                  # Application icons and visual assets
├── models/                  # [Manual Download Required] AI Neural Network Models (.onnx)
│   ├── face_detection_yunet_2023mar.onnx
│   └── face_recognition_sface_2021dec.onnx
├── modules/                 # Core business logic and engine components
│   ├── face_verifier.py     # OpenCV DNN Face Verification Engine
│   ├── ocsc_scraper.py      # Playwright-based background web scraper
│   ├── scanner_listener.py  # Background thread for OS-level barcode/QR listener
│   └── image_enhance.py     # Image pre-processing utilities (e.g., CLAHE)
├── ui/                      # Graphical User Interface (PyQt5)
│   └── main_window.py       # Main dashboard, UI layouts, and logic
├── config.json              # Administrator configuration file
├── Deployment_Guide.md      # Documentation for production build and deployment
├── main.py                  # Application entry point
├── requirements.txt         # Python dependency requirements
├── build.bat                # Windows batch script for compiling to .exe
└── setup.iss                # Script for Inno Setup installer creation
```

---

## 💻 Development Setup

To run the project locally or contribute as a developer, please follow these steps:

### 1. Install Dependencies
Ensure you have Python 3.8 or newer installed. Install the required libraries using pip:
```bash
pip install -r requirements.txt
```
*Note: Since the project uses Playwright for web scraping, you also need to install the browser binaries using:*
```bash
playwright install
```

### 2. Download AI Models
The application relies on specific ONNX models for the computer vision engine to function. Please download them and place them in the `models/` directory:
- [YuNet Face Detector (.onnx)](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [SFace Face Recognition (.onnx)](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)

### 3. Run the Application
Launch the system via the main entry point:
```bash
python main.py
```

---

## 📦 Production Deployment

The project can be completely bundled into a single standalone installer (`EDFVS_Setup_v1.0.exe`), allowing clients or examination centers to install and use the application without requiring Python, internet access, or manual environment setup.

For detailed instructions on packaging the application, please refer to the **[Deployment_Guide.md](./Deployment_Guide.md)**. The guide covers two main steps:
1. Compiling the project using PyInstaller (via `build.bat`).
2. Creating the setup wizard using Inno Setup (via `setup.iss`).

---

## 🔧 Administrator Configuration

Administrators can modify the behavior of the system by editing `config.json`. Key parameters include:
- `"match_threshold"`: The minimum cosine similarity score required for a match. Lower values mean **stricter** verification (Default: `0.35`).
- `"camera_index"`: The hardware index of the active webcam (`0` for primary, `1` for secondary).
- `"auto_reset_delay"`: The number of seconds the result screen remains visible before automatically resetting for the next scan (e.g., `3` seconds).
- `"clahe_clip_limit"` & `"clahe_grid_size"`: Parameters for refining image lighting and contrast automatically.
