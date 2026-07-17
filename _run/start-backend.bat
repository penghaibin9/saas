@echo off
cd /d "C:\Users\10850\Desktop\职校学生全生命周期系统\backend"
"C:\Users\10850\Desktop\职校学生全生命周期系统\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "C:\Users\10850\Desktop\职校学生全生命周期系统\_run\backend.log" 2>&1
