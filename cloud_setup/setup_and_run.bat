@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Initialize setup tracking (prevents premature execution of end section)
:: ============================================================================
set "SETUP_STARTED=1"
set "SETUP_COMPLETE=0"

:: ============================================================================
:: Fix working directory when run as administrator
:: When run as admin via right-click, Windows starts in System32
:: ============================================================================
:: Change to script's directory first (if script is in a known location)
:: Otherwise, change to Desktop which is where the script should be copied
pushd "%~dp0" 2>nul
if errorlevel 1 (
    :: If pushd fails, try Desktop
    pushd "%USERPROFILE%\Desktop" 2>nul
)

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
:: Complete Setup and Run Script with Timing
:: ============================================================================
:: This script performs the complete setup and launches the study
:: ============================================================================

:: Start overall timer
set "START_TIME=%TIME%"
echo ============================================================================
echo Starting setup at %START_TIME%
echo ============================================================================
echo.

:: 1. Check for Administrator Privileges
echo [STEP 1/9] Checking for administrator privileges...
set "STEP_START=%TIME%"
net session >nul 2>&1
if %errorlevel% == 0 (
    echo Administrator privileges detected.
) else (
    echo ERROR: This script requires administrator privileges.
    echo Please right-click the script and select "Run as administrator".
    pause
    exit /b 1
)
call :ShowElapsedTime "%STEP_START%"
echo.
echo [DEBUG] Step 1 completed, proceeding to Step 2...

:: Define file paths
set "PYTHON_INSTALLER=%TEMP%\python_installer.exe"
set "OPENVPN_INSTALLER=%TEMP%\openvpn.msi"
set "GIT_INSTALLER=%TEMP%\git_installer.exe"

:: 2. Download OpenVPN Installer
echo [STEP 2/9] Downloading OpenVPN Installer...
echo [DEBUG] Starting Step 2...
set "STEP_START=%TIME%"
curl -L -o "%OPENVPN_INSTALLER%" "https://swupdate.openvpn.org/community/releases/OpenVPN-2.6.15-I001-amd64.msi"
if %errorlevel% neq 0 (
    echo ERROR: Failed to download OpenVPN installer.
    pause
    exit /b 1
)
call :ShowElapsedTime "%STEP_START%"
echo.
echo [DEBUG] Step 2 completed, proceeding to Step 3...

:: 3. Download and Install Python 3.11
echo [STEP 3/9] Downloading and Installing Python 3.11...
echo [DEBUG] Starting Step 3...
set "STEP_START=%TIME%"
curl -L -o "%PYTHON_INSTALLER%" "https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
if %errorlevel% neq 0 (
    echo ERROR: Failed to download Python installer.
    pause
    exit /b 1
)

echo Installing Python 3.11 silently...
start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if %errorlevel% neq 0 (
    echo WARNING: Python installer returned error code %errorlevel%, but continuing...
)
:: Small delay to ensure installation completes
timeout /t 2 /nobreak >nul
echo Python installation finished.
:: Explicit check to prevent premature execution
if "%SETUP_COMPLETE%"=="1" (
    echo ERROR: SETUP_COMPLETE flag is incorrectly set! This should not happen.
    pause
    exit /b 1
)
call :ShowElapsedTime "%STEP_START%"
echo.
echo [DEBUG] Step 3 completed, proceeding to Step 4...

:: 4. Install gdown
echo [STEP 4/9] Installing gdown utility...
echo [DEBUG] Starting Step 4...
set "STEP_START=%TIME%"
"C:/Program Files/Python311/python.exe" -m pip install gdown
if %errorlevel% neq 0 (
    echo ERROR: Failed to install gdown.
    pause
    exit /b 1
)
call :ShowElapsedTime "%STEP_START%"
echo.
echo [DEBUG] Step 4 completed, proceeding to Step 5...

:: 5. Download and Install Sim4Life
echo [STEP 5/9] Downloading and Installing Sim4Life...
echo [DEBUG] Starting Step 5...
set "STEP_START=%TIME%"
set "SIM4LIFE_ZIP=%TEMP%\Sim4Life.zip"
"C:/Program Files/Python311/python.exe" -m gdown "YOUR_PRIVATE_GDRIVE_FILE_ID" -O "%SIM4LIFE_ZIP%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to download Sim4Life installer.
    pause
    exit /b 1
)

echo Unzipping Sim4Life installer...
set "SIM4LIFE_DIR=%TEMP%\Sim4Life"
mkdir "%SIM4LIFE_DIR%"
tar -xf "%SIM4LIFE_ZIP%" -C "%SIM4LIFE_DIR%"

echo Installing Sim4Life silently...
:: Verify installer exists before launching
if not exist "%SIM4LIFE_DIR%\Sim4Life_setup_8.2.0.16876.exe" (
    echo ERROR: Sim4Life installer not found at: %SIM4LIFE_DIR%\Sim4Life_setup_8.2.0.16876.exe
    pause
    exit /b 1
)
start /wait "" "%SIM4LIFE_DIR%\Sim4Life_setup_8.2.0.16876.exe" /S

echo Cleaning up Sim4Life installer files...
del "%SIM4LIFE_ZIP%"
rmdir /s /q "%SIM4LIFE_DIR%"
call :ShowElapsedTime "%STEP_START%"
echo.
echo [DEBUG] Step 5 completed, proceeding to Step 6...

:: 6. Download VPN Configuration Files
echo [STEP 6/9] Downloading VPN configuration files from Google Drive...
echo [DEBUG] Starting Step 6...
set "STEP_START=%TIME%"
"C:/Program Files/Python311/python.exe" -m gdown "https://drive.google.com/drive/folders/YOUR_PRIVATE_GDRIVE_FOLDER_ID" --folder -O .
if %errorlevel% neq 0 (
    echo ERROR: Failed to download VPN configuration files.
    pause
    exit /b 1
)
call :ShowElapsedTime "%STEP_START%"
echo.

:: 7. Install OpenVPN and Connect
echo [STEP 7/9] Installing OpenVPN and Connecting to VPN...
set "STEP_START=%TIME%"
echo Installing OpenVPN silently...
msiexec /i "%OPENVPN_INSTALLER%" /quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install OpenVPN.
    pause
    exit /b 1
)

if not exist "%DESKTOP_PATH%\certs\Intec-iGent.ovpn" (
    echo ERROR: Intec-iGent.ovpn not found in the 'certs' directory on Desktop.
    pause
    exit /b 1
)

echo Creating credentials file...
set "AUTH_FILE=%DESKTOP_PATH%\certs\openvpn_auth.txt"
(
    echo YOUR_VPN_USERNAME
    echo YOUR_VPN_PASSWORD
) > "%AUTH_FILE%"

echo Launching OpenVPN with the specified profile...
cd /d "%DESKTOP_PATH%\certs"

:: Verify OpenVPN is installed before launching
set "OPENVPN_EXE=C:\Program Files\OpenVPN\bin\openvpn.exe"
if not exist "%OPENVPN_EXE%" (
    echo ERROR: OpenVPN executable not found at: %OPENVPN_EXE%
    echo OpenVPN installation may have failed. Please install OpenVPN manually.
    pause
    exit /b 1
)

start "OpenVPN" "%OPENVPN_EXE%" --config "Intec-iGent.ovpn" --auth-user-pass "openvpn_auth.txt"

echo Waiting for connection to establish...
timeout /t 30 /nobreak >nul
call :ShowElapsedTime "%STEP_START%"
echo.

:: 8. Install Git and Clone Repository
echo [STEP 8/9] Installing Git and Cloning Repository...
set "STEP_START=%TIME%"

echo Downloading Git installer...
curl -L -o "%GIT_INSTALLER%" "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
if %errorlevel% neq 0 (
    echo ERROR: Failed to download Git installer.
    pause
    exit /b 1
)

echo Installing Git silently...
start /wait "" "%GIT_INSTALLER%" /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /Components="gitlfs"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Git.
    pause
    exit /b 1
)

:: Wait a moment for Git installation to fully complete and register
echo Waiting for Git installation to complete...
timeout /t 3 /nobreak >nul

:: Verify Git is installed and accessible
set "GIT_BIN=C:\Program Files\Git\bin\git.exe"
if not exist "%GIT_BIN%" (
    echo ERROR: Git installation not found at expected location: %GIT_BIN%
    pause
    exit /b 1
)

echo Cloning GOLIAT repository...
cd /d C:\Users\%CURRENT_USER%
"%GIT_BIN%" clone https://github.com/YOUR_USERNAME/goliat
if %errorlevel% neq 0 (
    echo ERROR: Failed to clone repository.
    pause
    exit /b 1
)
call :ShowElapsedTime "%STEP_START%"
echo.

:: 9. Setup Complete - Launch License Installer and Git Bash in Parallel
echo [STEP 9/9] Setup Complete - Launching License Installer and Git Bash...
set "STEP_START=%TIME%"
echo.

:: Set a flag to indicate all steps are complete (prevents accidental execution)
set "SETUP_COMPLETE=1"

:: Calculate and display total setup time
call :ShowElapsedTime "%START_TIME%" "TOTAL SETUP TIME"

echo ============================================================================
echo Setup complete! Launching license installer and Git Bash in parallel...
echo ============================================================================
echo.

:: Verify we actually completed all steps (safety check)
if "%SETUP_COMPLETE%" neq "1" (
    echo ERROR: Script execution error - setup not properly completed!
    echo SETUP_COMPLETE=%SETUP_COMPLETE%
    pause
    exit /b 1
)

:: Launch Git Bash in the goliat directory
cd /d C:\Users\%CURRENT_USER%\goliat

:: Verify bash.exe exists before launching (double check)
set "BASH_EXE=C:\Program Files\Git\bin\bash.exe"
set "BASH_EXISTS=0"

:: Check if bash.exe exists
if exist "%BASH_EXE%" (
    set "BASH_EXISTS=1"
) else (
    :: Also check alternative Git installation paths
    if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
        set "BASH_EXE=C:\Program Files (x86)\Git\bin\bash.exe"
        set "BASH_EXISTS=1"
    )
)

:: If bash.exe doesn't exist, show error and exit
if "%BASH_EXISTS%"=="0" (
    echo ============================================================================
    echo ERROR: Git Bash not found!
    echo ============================================================================
    echo Git Bash executable not found at expected location: C:\Program Files\Git\bin\bash.exe
    echo.
    echo This means Git was not installed successfully, or the installation path is different.
    echo.
    echo Please ensure Git is properly installed before launching the study.
    echo You can manually launch Git Bash and navigate to:
    echo   C:\Users\%CURRENT_USER%\goliat
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

:: Final verification before launching
if not exist "%BASH_EXE%" (
    echo ERROR: Git Bash executable verification failed!
    pause
    exit /b 1
)

:: Create a temporary initialization script for bash
set "INIT_SCRIPT=%TEMP%\goliat_init_%RANDOM%.sh"
(
    echo cd /c/Users/%CURRENT_USER%/goliat
    echo source .bashrc
    echo python -m pip install -e .
    echo git config --add safe.directory C:/Users/%CURRENT_USER%/goliat
    echo git config --global user.email "YOUR_EMAIL@example.com"
    echo git config --global user.name "YOUR_NAME"
    echo goliat init
    echo exec bash --login -i
) > "%INIT_SCRIPT%"

:: Convert Windows temp path to Git Bash format (C:\Users\... -> /c/Users/...)
set "INIT_SCRIPT_BASH=%INIT_SCRIPT:C:\=/c/%"
set "INIT_SCRIPT_BASH=%INIT_SCRIPT_BASH:\=/%"

:: Launch License Installer (non-blocking)
echo Launching Sim4Life License Installer...
set "LICENSE_PATH=C:\Users\Public\Documents\ZMT\Licensing Tools\8.2\LicenseInstall.exe"
if exist "%LICENSE_PATH%" (
    start "" "%LICENSE_PATH%"
    echo License installer launched.
) else (
    echo WARNING: License installer not found at: %LICENSE_PATH%
    echo Please navigate to the license installer manually.
)
echo.

:: Launch Git Bash with initialization commands (non-blocking)
echo Launching Git Bash with initialization commands...
echo Executing commands from start.sh...
cmd /c start "GOLIAT" "%BASH_EXE%" -c "source '%INIT_SCRIPT_BASH%'" 2>nul
if %errorlevel% neq 0 (
    echo WARNING: Failed to launch Git Bash. You may need to launch it manually.
    echo Navigate to: C:\Users\%CURRENT_USER%\goliat
    echo.
    echo You can manually launch Git Bash and run:
    echo   cd C:\Users\%CURRENT_USER%\goliat
) else (
    echo Git Bash launched successfully.
)
echo.

call :ShowElapsedTime "%STEP_START%"
echo.
echo ============================================================================
echo Both license installer and Git Bash have been launched!
echo You can install the license while working in the Git Bash terminal.
echo ============================================================================
pause
endlocal
exit /b 0

:: ============================================================================
:: Function to calculate and display elapsed time
:: ============================================================================
:ShowElapsedTime
setlocal
set "START=%~1"
set "LABEL=%~2"

:: Get current time
set "END=%TIME%"

:: Convert times to centiseconds
call :TimeToCs "%START%" START_CS
call :TimeToCs "%END%" END_CS

:: Calculate difference
set /a "DIFF_CS=END_CS-START_CS"

:: Handle negative difference (crossed midnight)
if !DIFF_CS! lss 0 set /a "DIFF_CS+=8640000"

:: Convert back to hours, minutes, seconds, centiseconds
set /a "HOURS=DIFF_CS/360000"
set /a "MINS=(DIFF_CS%%360000)/6000"
set /a "SECS=(DIFF_CS%%6000)/100"
set /a "CS=DIFF_CS%%100"

:: Format output
if "%LABEL%"=="" (
    echo Completed in %HOURS%h %MINS%m %SECS%.%CS%s
) else (
    echo %LABEL%: %HOURS%h %MINS%m %SECS%.%CS%s
)

endlocal
exit /b 0

:: ============================================================================
:: Function to convert time to centiseconds
:: ============================================================================
:TimeToCs
setlocal
set "TIME_STR=%~1"

:: Remove leading zeros to prevent octal interpretation
for /f "tokens=1-4 delims=:,. " %%a in ("%TIME_STR%") do (
    set /a "H=100%%a%%100"
    set /a "M=100%%b%%100"
    set /a "S=100%%c%%100"
    set /a "C=100%%d%%100"
)

:: Calculate total centiseconds
set /a "TOTAL_CS=(H*360000)+(M*6000)+(S*100)+C"

endlocal & set "%~2=%TOTAL_CS%"
exit /b 0
