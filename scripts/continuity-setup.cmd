@echo off
rem Double-click to set up session continuity. See docs\continuity.md.
setlocal
set "SBO=%~dp0..\.venv\Scripts\sbo-continuity.exe"
if not exist "%SBO%" set "SBO=sbo-continuity"
set "CHOME=%SIS_CONTINUITY_HOME%"
if "%CHOME%"=="" set "CHOME=%USERPROFILE%\.starlight\continuity"
"%SBO%" setup %*
if not errorlevel 1 if exist "%CHOME%\trust-policy.draft.json" if not exist "%CHOME%\trust-policy.json" "%SBO%" approve
echo.
"%SBO%" doctor
echo.
pause
