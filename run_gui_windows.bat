@echo off
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0capcut_captions_gui.py"
) else (
    start "" python "%~dp0capcut_captions_gui.py"
)
