cd .\venv\Scripts\
activate.bat
:start
python run.py
ping 127.0.0.1 -n 300 >nul
goto start