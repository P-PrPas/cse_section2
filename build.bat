@echo off
setlocal

pushd "%~dp0"

echo =========================================
echo EDFVS Build Script
echo =========================================

set "APP_NAME=EDFVS"
set "APP_VERSION=1.0.0"
set "OUTPUT_DIR=%CD%\Output"
set "PORTABLE_ROOT=%OUTPUT_DIR%\%APP_NAME%_Portable_v%APP_VERSION%"
set "PORTABLE_APP_DIR=%PORTABLE_ROOT%\%APP_NAME%"
set "PORTABLE_ZIP=%OUTPUT_DIR%\%APP_NAME%_Portable_v%APP_VERSION%.zip"
set "PYTHON_EXE="
set "STORE_SITE_PACKAGES=%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages"
set "PLAYWRIGHT_BROWSERS_DIR=%LOCALAPPDATA%\ms-playwright"
set "PLAYWRIGHT_STAGE_DIR=%CD%\build_assets\ms-playwright"
for %%I in (
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python313"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
) do (
    if exist "%%~fI\python.exe" if not defined PYTHON_EXE set "PYTHON_EXE=%%~fI\python.exe"
)

if not defined PYTHON_EXE (
    for /f "delims=" %%I in ('where python.exe 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
    )
)

if not defined PYTHON_EXE (
    echo ERROR: python.exe not found.
    echo Install Python 3.12+ first, then run this script again.
    popd
    exit /b 1
)

if exist "%STORE_SITE_PACKAGES%" (
    if defined PYTHONPATH (
        set "PYTHONPATH=%STORE_SITE_PACKAGES%;%PYTHONPATH%"
    ) else (
        set "PYTHONPATH=%STORE_SITE_PACKAGES%"
    )
)

echo 1. Checking dependencies...
"%PYTHON_EXE%" -c "import PyQt5, cv2, requests, pynput, numpy, fitz, PyInstaller, playwright, dotenv"
if errorlevel 1 (
    echo Required Python packages are missing.
    echo Attempting to install from requirements.txt...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 goto :build_failed
)

echo.
echo 2. Cleaning old builds...
rmdir /s /q build dist 2>nul
rmdir /s /q build_assets 2>nul
if exist "%PORTABLE_ROOT%" rmdir /s /q "%PORTABLE_ROOT%"
if exist "%PORTABLE_ZIP%" del /q "%PORTABLE_ZIP%"
del /q EDFVS.spec 2>nul

echo.
echo 3. Validating Playwright Chromium bundle...
echo Using: %PYTHON_EXE%
if not exist "%PLAYWRIGHT_BROWSERS_DIR%" (
    echo ERROR: Playwright browser files not found in "%PLAYWRIGHT_BROWSERS_DIR%".
    echo Run "playwright install chromium" on the build machine first.
    goto :build_failed
)

"%PYTHON_EXE%" -c "from pathlib import Path; import os, sys; root = Path(os.environ['PLAYWRIGHT_BROWSERS_DIR']); candidates = sorted(root.glob('chromium-*')); assert candidates, 'No chromium-* folder found'; browser = candidates[-1] / 'chrome-win64'; required = [browser / 'chrome.exe', browser / 'resources.pak', browser / 'icudtl.dat']; missing = [str(p) for p in required if not p.exists() or p.stat().st_size == 0]; assert not missing, 'Missing or empty Chromium files: ' + ', '.join(missing); print(browser)"
if errorlevel 1 goto :build_failed

set "PLAYWRIGHT_BROWSERS_PATH=%PLAYWRIGHT_BROWSERS_DIR%"
"%PYTHON_EXE%" -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); browser = p.chromium.launch(headless=True); browser.close(); p.stop(); print('Playwright Chromium smoke test passed.')"
if errorlevel 1 (
    echo ERROR: Playwright Chromium launch test failed.
    echo Reinstall the browser bundle with: python -m playwright install chromium
    goto :build_failed
)

echo.
echo 4. Staging Playwright browser files...
robocopy "%PLAYWRIGHT_BROWSERS_DIR%" "%PLAYWRIGHT_STAGE_DIR%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo ERROR: Failed to copy Playwright browser files into staging.
    goto :build_failed
)

"%PYTHON_EXE%" -c "from pathlib import Path; import sys; root = Path(r'%PLAYWRIGHT_STAGE_DIR%'); pak_files = list(root.rglob('resources.pak')); assert pak_files, 'resources.pak not found in staged browser bundle'; bad = [str(p) for p in pak_files if p.stat().st_size < 1024]; assert not bad, 'Invalid staged resources.pak: ' + ', '.join(bad); [p.open('rb').read(4096) for p in pak_files]; print('Staged browser files verified.')"
if errorlevel 1 goto :build_failed

echo.
echo 5. Building executable with PyInstaller...
echo This may take a few minutes...
:: Using --onedir for faster startup, OpenCV/DNN works best this way
:: --noconsole hides the terminal window
"%PYTHON_EXE%" -m PyInstaller --noconfirm --onedir --windowed ^
    --name "EDFVS" ^
    --exclude-module "PySide6" ^
    --exclude-module "PySide2" ^
    --exclude-module "PyQt6" ^
    --add-data="config.json:." ^
    --add-data="models:models" ^
    --add-data="ui:ui" ^
    --add-data="%PLAYWRIGHT_STAGE_DIR%:ms-playwright" ^
    main.py
if errorlevel 1 goto :build_failed

if not exist "dist\%APP_NAME%\%APP_NAME%.exe" goto :build_failed

echo.
echo 6. Packaging portable release...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
mkdir "%PORTABLE_ROOT%"
robocopy "dist\%APP_NAME%" "%PORTABLE_APP_DIR%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo ERROR: Failed to stage portable application files.
    goto :build_failed
)

(
echo @echo off
echo pushd "%%~dp0%APP_NAME%"
echo start "" "%APP_NAME%.exe"
echo popd
) > "%PORTABLE_ROOT%\Run_%APP_NAME%.bat"

(
echo EDFVS Portable Package
echo ======================
echo 1. Extract this ZIP to a normal folder on the client machine.
echo 2. Open the extracted folder.
echo 3. Run Run_%APP_NAME%.bat or %APP_NAME%\%APP_NAME%.exe.
echo 4. Do not run the app directly from inside the ZIP viewer.
echo.
echo Notes:
echo - No Python installation is required on the client machine.
echo - Keep the %APP_NAME% folder structure unchanged.
echo - Runtime logs will be written outside the app folder automatically.
) > "%PORTABLE_ROOT%\README_PORTABLE.txt"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%PORTABLE_ROOT%\*' -DestinationPath '%PORTABLE_ZIP%' -Force"
if errorlevel 1 (
    echo ERROR: Failed to create portable ZIP package.
    goto :build_failed
)

echo.
echo =========================================
echo Build complete!
echo Portable folder: %PORTABLE_ROOT%
echo Portable ZIP:    %PORTABLE_ZIP%
echo =========================================
popd
pause
exit /b 0

:build_failed
echo.
echo =========================================
echo Build failed. Check the error messages above.
echo =========================================
popd
pause
exit /b 1
