@echo off
setlocal enabledelayedexpansion

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
echo [STEP 1/8] Checking for administrator privileges...
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
echo [STEP 2/10] Downloading OpenVPN Installer...
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
echo [STEP 3/10] Downloading and Installing Python 3.11...
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
echo Python installation finished.
call :ShowElapsedTime "%STEP_START%"
echo.
echo [DEBUG] Step 3 completed, proceeding to Step 4...

:: 4. Install gdown
echo [STEP 4/10] Installing gdown utility...
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
echo [STEP 5/10] Downloading and Installing Sim4Life...
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
start /wait "" "%SIM4LIFE_DIR%\Sim4Life_setup_8.2.0.16876.exe" /S

echo Cleaning up Sim4Life installer files...
del "%SIM4LIFE_ZIP%"
rmdir /s /q "%SIM4LIFE_DIR%"
call :ShowElapsedTime "%STEP_START%"
echo.
echo [DEBUG] Step 5 completed, proceeding to Step 6...

:: 6. Download VPN Configuration Files
echo [STEP 6/10] Downloading VPN configuration files from Google Drive...
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
echo [STEP 7/10] Installing OpenVPN and Connecting to VPN...
set "STEP_START=%TIME%"
echo Installing OpenVPN silently...
msiexec /i "%OPENVPN_INSTALLER%" /quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install OpenVPN.
    pause
    exit /b 1
)

if not exist "%~dp0certs\Intec-iGent.ovpn" (
    echo ERROR: Intec-iGent.ovpn not found in the 'certs' directory.
    pause
    exit /b 1
)

echo Creating credentials file...
set "AUTH_FILE=%~dp0certs\openvpn_auth.txt"
(
    echo YOUR_VPN_USERNAME
    echo YOUR_VPN_PASSWORD
) > "%AUTH_FILE%"

echo Launching OpenVPN with the specified profile...
cd /d "%~dp0certs"
start "OpenVPN" "C:\Program Files\OpenVPN\bin\openvpn.exe" --config "Intec-iGent.ovpn" --auth-user-pass "openvpn_auth.txt"

echo Waiting for connection to establish...
timeout /t 30 /nobreak >nul
call :ShowElapsedTime "%STEP_START%"
echo.

:: 8. Install Sim4Life License
echo [STEP 8/10] Installing Sim4Life License...
set "STEP_START=%TIME%"
echo.
echo ============================================================================
echo LICENSE INSTALLATION REQUIRED
echo ============================================================================
echo Please install the Sim4Life license manually using the GUI.
echo The license installer should be located at:
echo C:\Users\Public\Documents\ZMT\Licensing Tools\8.2\LicenseInstall.exe
echo.
echo Opening the license installer location...
set "LICENSE_PATH=C:\Users\Public\Documents\ZMT\Licensing Tools\8.2\LicenseInstall.exe"
if exist "%LICENSE_PATH%" (
    start "" "%LICENSE_PATH%"
) else (
    echo WARNING: License installer not found at: %LICENSE_PATH%
    echo Please navigate to the license installer manually.
)
echo.
echo After installing the license, press any key to continue...
pause >nul
call :ShowElapsedTime "%STEP_START%"
echo.

:: 9. Install Git and Clone Repository
echo [STEP 9/10] Installing Git and Cloning Repository...
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

echo Cloning GOLIAT repository...
cd /d C:\Users\user
"C:\Program Files\Git\bin\git.exe" clone https://github.com/YOUR_USERNAME/goliat
if %errorlevel% neq 0 (
    echo ERROR: Failed to clone repository.
    pause
    exit /b 1
)
call :ShowElapsedTime "%STEP_START%"
echo.

:: 10. Setup Complete
echo [STEP 10/10] Setup Complete
set "STEP_START=%TIME%"
call :ShowElapsedTime "%STEP_START%"
echo.

:: Calculate and display total setup time
call :ShowElapsedTime "%START_TIME%" "TOTAL SETUP TIME"

echo ============================================================================
echo Setup complete! Now launching the study...
echo ============================================================================
echo.

:: Create a custom bashrc that sources the normal one and runs the command
echo Creating custom bashrc for GOLIAT...
set "CUSTOM_RC=C:\Users\user\goliat\.bashrc_auto"
(
    echo # Source the normal bashrc if it exists
    echo if [ -f ~/.bashrc ]; then
    echo     source ~/.bashrc
    echo fi
    echo.
    echo # Source the project bashrc if it exists
    echo if [ -f .bashrc ]; then
    echo     source .bashrc
    echo fi
    echo.
    echo # Run the study
    echo echo "============================================"
    echo echo "Running GOLIAT study..."
    echo echo "============================================"
    echo goliat study near_field_config
    echo.
    echo # Keep interactive shell after command
    echo echo ""
    echo echo "Study completed. Bash shell is ready for use."
    echo PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
) > "%CUSTOM_RC%"

:: Launch Git Bash with custom rcfile in the goliat directory
cd /d C:\Users\user\goliat
start "GOLIAT Study" "C:\Program Files\Git\bin\bash.exe" --rcfile ".bashrc_auto" -i

echo Study launched in separate window.
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