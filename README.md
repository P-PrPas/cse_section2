# CSE_Section2: Exam Face Verification System (EDFVS)

This is a premium, offline-first student identity verification system designed for the ก.พ. (OCSC) exam environment.

## Features
- **Modern Premium UI**: Slate dark theme with dynamic status indicators.
- **Real-time Face Verification**: High-performance face detection and comparison using OpenCV YuNet and SFace models.
- **Smart QR Scanning**: Automates document fetching from various sources (Google Drive, Me-QR, etc.).
- **Camera Selection**: Support for multiple webcam devices via hardware description dropdown.
- **Accuracy Optimization**: Balanced thresholds for real-world expression variations.

## Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Download models into the `models/` directory (YuNet & SFace ONNX).
3. Run the application:
   ```bash
   python main.py
   ```
