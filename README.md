# EDFVS: Exam Document Face Verification System

**EDFVS** เป็นระบบตรวจสอบและยืนยันตัวตนของผู้เข้าสอบแบบออฟไลน์ (Offline-first Verification System) ถูกออกแบบมาเพื่องานยืนยันตัวตนระดับองค์กร เช่น การสอบของสำนักงาน ก.พ. (OCSC) 
ตัวระบบทำงานผ่านกล้อง Webcam ด้วยประสิทธิภาพสูง โดยตรวจสอบความตรงกันระหว่าง "ใบหน้าจากกล้องถ่ายทอดสด" และ "เอกสารประจำตัว/บัตรสอบ" ที่ดึงข้อมูลผ่านการสแกน QR Code (รองรับไฟล์ภาพและไฟล์ PDF)

ด้วยการใช้สถาปัตยกรรม Local Computer Vision ทำให้องค์กรสามารถมั่นใจในความเป็นส่วนตัว (Privacy-first) และความเชื่อใจได้ว่าข้อมูลจะไม่ถูกส่งออกสู่อินเทอร์เน็ตระหว่างกระบวนการตรวจสอบ

---

## ✨ Features (คุณสมบัติเด่น)

- **⚡ Offline-First AI Engine**: ประมวลผลแบบเบ็ดเสร็จในตัวเครื่องโดยไม่ต้องใช้อินเทอร์เน็ต หมดปัญหาเรื่องข้อมูลหลุดรั่ว
- **🎭 Real-time Face Detection & Recognition**: ทำงานอย่างรวดเร็วด้วย **OpenCV DNN** ที่ผ่านการ Optimization ร่วมกับโมเดล 
  - *YuNet (2023)* - ตรวจจับใบหน้าได้อย่างรวดเร็ว
  - *SFace (2021)* - สหสัมพันธ์และเปรียบเทียบรูปหน้าอย่างแม่นยำ
- **📂 Smart Document Scanner (QR Code)**: ตรวจจับและอ่าน QR Code แบบอัตโนมัติ พร้อมดึงข้อมูลเอกสารยืนยันตัวของนักเรียน ไม่ว่าจะเป็นไฟล์ภาพทั่วไป หรือแม่แต่ไฟล์ **PDF (ผ่าน PyMuPDF)**
- **🎨 Premium Dark UI**: หน้าจอการทำงานถูกออกแบบใหม่ในสไตล์ "Modern Slate / Tailwind-inspired" ซึ่งใช้สถานะสี แถบโหลดหน้าข้อมูล และกรอบ Reticle บอกสถานะอย่างทันสมัย อ่านง่าย ลดภาระผู้คุมสอบ
- **⚙️ Dynamic Hardware Configuration**: รองรับการเลือกกล้อง Webcam หลายตัวแบบอิสระในตัว พร้อมระบบกันการจัดสรรหน่วยความจำ OpenBLAS ผิดพลาดผ่านข้อจำกัด CPU Thread
- **🛠️ Self-Configuration (`config.json`)**: ผู้ใช้งานระดับ System Admin สามารถตั้งค่าความหน่วงของหน้าจอ หรือปรับระดับ Threshold ระดับความเข้มงวดในการตรวจใบหน้าผ่านไฟล์ตั้งค่าได้อย่างง่ายดาย

---

## 🏗️ โครงสร้างของโปรเจกต์ (Directory Structure)

```text
CSE_Section2/
├── assets/                  # (Optional) ไอคอนแอปพลิเคชันต่างๆ
├── models/                  # [ต้องดาวน์โหลดเพิ่ม] โมเดล AI (.onnx)
│   ├── face_detection_yunet_2023mar.onnx
│   └── face_recognition_sface_2021dec.onnx
├── modules/                 # ลอจิกหลักของการตรวจสอบใบหน้า และแยกไฟล์
│   └── face_verifier.py     # โมดูลระบบ Engine (OpenCV)
├── ui/                      # ส่วนจัดการ UI (PyQt5)
│   └── main_window.py       # คลาสหน้าต่างและ Widget ย่อย
├── config.json              # ไฟล์ตั้งค่าสำหรับ Admin (Threshold, Delay, etc.)
├── Deployment_Guide.md      # คู่มือการส่งมอบโปรเจกต์ (Build & Install)
├── main.py                  # ไฟล์ Entry Point เริ่มต้นระบบ
├── requirements.txt         # ไฟล์ระบุ Dependencies สำหรับนักพัฒนา
├── build.bat                # สคริปต์คอมไพล์โปรแกรม (.exe)
└── setup.iss                # สคริปต์สร้างตัวติดตั้ง (Setup Wizard)
```

---

## 💻 การติดตั้งและใช้งานสำหรับนักพัฒนา (Development Setup)

หากคุณต้องการรันโค้ดโปรเจกต์ หรือปรับปรุงแก้ไขในฐานะนักพัฒนา ให้ทำตามขั้นตอนต่อไปนี้:

### 1. ติดตั้ง Requirements
ตรวจเช็คให้แน่ใจว่าติดตั้ง Python 3.8+ แล้ว รันคำสั่งต่อไปนี้เพื่อติดตั้งไลบรารี:
```bash
pip install -r requirements.txt
```

### 2. ดาวน์โหลด Models
ระบบนี้ต้องการโมเดล AI ในการทำงาน กรุณาดาวน์โหลดแล้วนำไปใส่ไว้ในโฟลเดอร์ `models/`:
- [YuNet Face Detector (.onnx)](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [SFace Face Recognition (.onnx)](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)

### 3. รันโปรแกรม
```bash
python main.py
```

---

## 📦 การสร้างตัวติดตั้งใช้งานจริง (Production Deployment)
คุณสามารถนำโปรเจกต์นี้ สร้างเป็นไฟล์ `EDFVS_Setup_v1.0.exe` ไฟล์เดียว เพื่อส่งต่อให้ลูกค้านำไปติดตั้งและใช้งานได้ทันที แม้ไม่มีอินเทอร์เน็ต!

กรุณาอ่าน **[Deployment_Guide.md](./Deployment_Guide.md)** อย่างละเอียดเพื่อทำตามขั้นตอนสองขั้น:
1. การใช้ `build.bat` หรือ PyInstaller 
2. การใช้ `setup.iss` ควบคู่กับโปรแกรม Inno Setup

---

## 🔧 การตั้งค่าระดับแอดมิน (Configuration)
คุณสามารถแก้ไขไฟล์ `config.json` เพื่อเปลี่ยนพฤติกรรมของระบบ:
- `"match_threshold"`: ค่ายิ่งน้อยแปลว่า **"ยิ่งเข้มงวด"** (ค่าเริ่มต้น `0.35`)
- `"camera_index"`: อุปกรณ์กล้องหลัก (`0` = กล้องตัวแรก, `1` = ตัวที่สอง)
- `"auto_reset_delay"`: ระยะเวลาการโชว์หน้าจอความสำเร็จก่อนเริ่มคิวถัดไปอัตโนมัติ (เช่น `3` วินาที)
