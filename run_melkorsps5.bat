@echo off
title MelkorS PS5 Control Center
cd /d "%~dp0"
echo ========================================================
echo         Launching MelkorS PS5 Control Center
echo ========================================================
start "" pythonw gui\main.py
exit
