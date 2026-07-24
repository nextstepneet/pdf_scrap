@echo off
title NextStep NEET — Cutoff Extractor
echo.
echo  ======================================================
echo   NextStep NEET Cutoff Extractor
echo   Open http://localhost:5000 in your browser
echo  ======================================================
echo.
set PYTHONPATH=E:\NextStepNeet\Lib\site-packages
set PYTHONIOENCODING=utf-8
cd /d "E:\NextStepNeet\app"
C:\Python314\python.exe app.py
pause
