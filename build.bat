@echo off
echo =========================================
echo EDFVS Build Script
echo =========================================

echo 1. Installing dependencies (including PyInstaller)...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo 2. Cleaning old builds...
rmdir /s /q build dist 2>nul

echo.
echo 3. Building executable with PyInstaller...
echo This may take a few minutes...
:: Using --onedir for faster startup, OpenCV/DNN works best this way
:: --noconsole hides the terminal window
pyinstaller --noconfirm --onedir --windowed ^
    --name "EDFVS" ^
    --add-data "config.json;." ^
    --add-data "models;models" ^
    --add-data "ui;ui" ^
    main.py

echo.
echo =========================================
echo Build complete! Executable is in dist\EDFVS\EDFVS.exe
echo To create an installer, download Inno Setup from:
echo https://jrsoftware.org/isdl.php
echo Then open and run setup.iss!
echo =========================================
pause
