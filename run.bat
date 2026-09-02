@echo off
call C:\Users\cholo\anaconda3\Scripts\activate.bat commatour

cd /d C:\Users\cholo\commatour\backend

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload