@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py setup_wizard.py  & goto :eof)
where python >nul 2>nul && (python setup_wizard.py  & goto :eof)
echo.
echo  [!] Python was not found on this PC.
echo.
echo      Open Microsoft Store, search for "Python",
echo      and install Python 3.12 (free).
echo      Then double-click this file again.
echo.
pause
