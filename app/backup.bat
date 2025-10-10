@ECHO OFF
REM This script runs the Python backup process using the project's virtual environment.

ECHO Activating virtual environment and running Python backup script...

REM Get the directory of this batch file
SET "CURRENT_DIR=%~dp0"

REM Path to the Python executable in the virtual environment
SET "VENV_PYTHON=%CURRENT_DIR%.venv\Scripts\python.exe"

REM Path to the backup script
SET "BACKUP_SCRIPT=%CURRENT_DIR%backup.py"

REM Check if the venv python exists
IF NOT EXIST "%VENV_PYTHON%" (
    ECHO.
    ECHO !!! ERROR: Virtual environment Python not found at %VENV_PYTHON% !!!
    ECHO Please ensure the virtual environment is set up correctly.
    GOTO:EOF
)

REM Run the python script using the venv's python
"%VENV_PYTHON%" "%BACKUP_SCRIPT%"

ECHO.
ECHO Script execution finished.

:EOF
