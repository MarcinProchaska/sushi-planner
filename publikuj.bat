@echo off
rem Sushi Planner - publikacja na GitHuba (Windows).
rem Cala robota jest w publikuj.ps1; ten plik tylko go uruchamia, omijajac
rem domyslna polityke wykonywania skryptow.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publikuj.ps1"
