@echo off
echo Starting AI Voice Scheduler Backend...
set PYTHONPATH=%PYTHONPATH%;T:/calender/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
