@echo off
setlocal

:: ============================================================================
:: VPN Connection Script
:: ============================================================================
:: Assumes OpenVPN is already installed.
:: ============================================================================

:: Check for Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires administrator privileges.
    echo Please right-click the script and select "Run as administrator".
    pause
    exit /b 1
)

:: Check if VPN config exists
if not exist "%~dp0certs\Intec-iGent.ovpn" (
    echo ERROR: Intec-iGent.ovpn not found in the 'certs' directory.
    pause
    exit /b 1
)

:: Create credentials file
set "AUTH_FILE=%~dp0certs\openvpn_auth.txt"
(
    echo YOUR_VPN_USERNAME
    echo YOUR_VPN_PASSWORD
) > "%AUTH_FILE%"

:: Launch OpenVPN
cd /d "%~dp0certs"
start "OpenVPN" "C:\Program Files\OpenVPN\bin\openvpn.exe" --config "Intec-iGent.ovpn" --auth-user-pass "openvpn_auth.txt"

echo VPN connection initiated. Check connection status with: ipconfig /all
pause
endlocal

