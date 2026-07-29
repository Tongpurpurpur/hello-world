@echo off
REM Double-click launcher for the Flat White desktop pet (Windows).
REM Uses pythonw so no console window sticks around behind the pet.
cd /d "%~dp0"
start "" pythonw pet.py
