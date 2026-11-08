@echo off
rem Cria na Area de Trabalho o atalho "Solar ROI" que abre o app com um clique.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0criar_atalho.ps1"
