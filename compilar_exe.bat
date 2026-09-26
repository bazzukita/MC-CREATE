@echo off
echo.
echo ========================================
echo   Compilando Macros a EXE
echo ========================================
echo.

REM Instalar dependencias
echo [1/3] Instalando dependencias...
pip install customtkinter pynput CTkMessagebox pyinstaller --quiet

REM Compilar Basketball Legends Macro
echo.
echo [2/3] Compilando Basketball Legends Macro...
pyinstaller --onefile --windowed --icon=icon.ico --name "Basketball_Legends_Macro" --distpath "./dist" --buildpath "./build" --specpath "./build" basketball_macro_gui.py

REM Compilar Keyboard Macro General
echo.
echo [3/3] Compilando Keyboard Macro General...
pyinstaller --onefile --windowed --icon=icon.ico --name "Keyboard_Macro" --distpath "./dist" --buildpath "./build" --specpath "./build" keyboard_macro_gui.py

echo.
echo ========================================
echo   ✓ Compilación completada!
echo ========================================
echo.
echo Los archivos EXE están en: ./dist/
echo.
pause
