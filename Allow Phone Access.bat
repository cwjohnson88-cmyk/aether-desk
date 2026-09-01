@echo off
REM Opens inbound TCP 8791 so the Aether phone app can reach this PC on Wi-Fi.
REM Does not place trades. Paper blotter only. Token still required from the LAN.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator permission...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
netsh advfirewall firewall delete rule name="Aether Desk 8791" >nul 2>&1
netsh advfirewall firewall add rule name="Aether Desk 8791" dir=in action=allow protocol=TCP localport=8791 profile=private,domain
echo Done. Phone app talks to this PC on port 8791 (token required). Hermes stays on 8787.
pause
