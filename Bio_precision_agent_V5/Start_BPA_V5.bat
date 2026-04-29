@echo off
cd /d "%~dp0"
echo.
echo  ================================================
echo   Bio-Precision Agent V5
echo  ================================================
echo.

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set RAW_IP=%%a
    goto :got_ip
)
:got_ip
set LOCAL_IP=%RAW_IP: =%

echo  [LAN ]  Other devices : http://%LOCAL_IP%:8501
echo  [Local] This machine  : http://localhost:8501
echo  [Auth ]  User: admin   Pass: admin
echo.
echo  Starting service...
echo.

python -m streamlit run app.py ^
    --server.address=0.0.0.0 ^
    --server.port=8501 ^
    --server.headless=true ^
    --browser.gatherUsageStats=false

pause
