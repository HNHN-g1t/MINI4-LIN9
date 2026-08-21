@echo off
REM ---------------------------------------------------------------
REM  Race event update launcher.
REM  ASCII ONLY in this file. All Japanese messages come from Python
REM  (see event_notice.py) because .bat files garble Japanese text.
REM ---------------------------------------------------------------
setlocal
cd /d "%~dp0"
chcp 65001 >nul

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)

if not defined PY (
  echo.
  echo Python was not found on this PC.
  echo Please install Python from the Microsoft Store, then run this file again.
  echo   1. Open Microsoft Store
  echo   2. Search for "Python 3"
  echo   3. Install it
  echo.
  start "" "ms-windows-store://search/?query=Python%%203"
  pause
  exit /b 1
)

%PY% event_notice.py start

%PY% fetch_events.py
if errorlevel 1 goto failed

%PY% review_events.py
if errorlevel 1 goto failed

%PY% event_notice.py done
pause
exit /b 0

:failed
%PY% event_notice.py abort
pause
exit /b 1
