@echo off
setlocal

:: ============================================================================
:: Detect Username and Change to Desktop
:: ============================================================================
:: Automatically detect the current username
set "CURRENT_USER=%USERNAME%"
if "%CURRENT_USER%"=="" (
    echo ERROR: Could not detect username. USERNAME environment variable is not set.
    pause
    exit /b 1
)

:: Change to the user's Desktop directory
set "DESKTOP_PATH=C:\Users\%CURRENT_USER%\Desktop"
if not exist "%DESKTOP_PATH%" (
    echo ERROR: Desktop directory not found at: %DESKTOP_PATH%
    pause
    exit /b 1
)

cd /d "%DESKTOP_PATH%"
echo Changed to Desktop directory: %CD%
echo.

:: ============================================================================
:: Check NVIDIA GPU Drivers (nvidia-smi)
:: ============================================================================
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo ============================================================================
    echo ERROR: NVIDIA GPU drivers not detected!
    echo ============================================================================
    echo nvidia-smi failed to run. This indicates that NVIDIA GPU drivers
    echo are not installed or not working properly.
    echo.
    echo Please install NVIDIA GPU drivers manually before running this script.
    echo You can download the latest drivers from:
    echo https://www.nvidia.com/Download/index.aspx
    echo.
    echo After installing the drivers, restart your computer and try again.
    echo ============================================================================
    pause
    exit /b 1
)

:: ============================================================================
:: Check Computer Name
:: ============================================================================
if /i "%COMPUTERNAME%" neq "MYGCLOUDPC" if /i "%COMPUTERNAME%" neq "WIN10-NEW" (
    echo ============================================================================
    echo ERROR: Computer name mismatch!
    echo ============================================================================
    echo Current computer name: %COMPUTERNAME%
    echo Required computer name: MYGCLOUDPC or WIN10-NEW
    echo.
    echo You must rename this computer to "MYGCLOUDPC" or "WIN10-NEW" and restart before running this script.
    echo.
    echo To rename the computer from Administrator Command Prompt, run:
    echo     wmic computersystem where name="%COMPUTERNAME%" call rename name="MYGCLOUDPC"
    echo     OR
    echo     wmic computersystem where name="%COMPUTERNAME%" call rename name="WIN10-NEW"
    echo.
    echo After renaming, you MUST restart the computer for the change to take effect.
    echo ============================================================================
    pause
    exit /b 1
)

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
if not exist "%DESKTOP_PATH%\certs\Intec-iGent.ovpn" (
    echo ERROR: Intec-iGent.ovpn not found in the 'certs' directory on Desktop.
    pause
    exit /b 1
)

:: Create credentials file
set "AUTH_FILE=%DESKTOP_PATH%\certs\openvpn_auth.txt"
(
    echo YOUR_VPN_USERNAME
    echo YOUR_VPN_PASSWORD
) > "%AUTH_FILE%"

:: Launch OpenVPN
cd /d "%DESKTOP_PATH%\certs"

:: Verify OpenVPN is installed before launching
set "OPENVPN_EXE=C:\Program Files\OpenVPN\bin\openvpn.exe"
if not exist "%OPENVPN_EXE%" (
    echo ERROR: OpenVPN executable not found at: %OPENVPN_EXE%
    echo OpenVPN is not installed. Please install OpenVPN first.
    pause
    exit /b 1
)

start "OpenVPN" "%OPENVPN_EXE%" --config "Intec-iGent.ovpn" --auth-user-pass "openvpn_auth.txt"

echo VPN connection initiated. Check connection status with: ipconfig /all
pause
endlocal
