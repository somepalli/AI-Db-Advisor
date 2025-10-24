@echo off
echo ========================================
echo ClickHouse Manual Installation Script
echo ========================================
echo.

REM Create installation directory
set INSTALL_DIR=C:\clickhouse
echo Creating installation directory: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo.
echo ========================================
echo Step 1: Download ClickHouse
echo ========================================
echo.
echo Downloading ClickHouse Windows binary...
echo Please wait, this may take a few minutes...
echo.

REM Download using PowerShell
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://builds.clickhouse.com/master/amd64/clickhouse' -OutFile '%INSTALL_DIR%\clickhouse.exe'}"

if not exist "%INSTALL_DIR%\clickhouse.exe" (
    echo.
    echo ERROR: Download failed!
    echo.
    echo Please download manually from:
    echo https://github.com/ClickHouse/ClickHouse/releases
    echo.
    echo Look for: clickhouse-windows-amd64.zip or clickhouse.exe
    echo Extract to: %INSTALL_DIR%
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Step 2: Create Configuration Files
echo ========================================
echo.

REM Create config directory
if not exist "%INSTALL_DIR%\config.d" mkdir "%INSTALL_DIR%\config.d"

REM Create basic config file
echo ^<?xml version="1.0"?^> > "%INSTALL_DIR%\config.xml"
echo ^<clickhouse^> >> "%INSTALL_DIR%\config.xml"
echo     ^<logger^> >> "%INSTALL_DIR%\config.xml"
echo         ^<level^>information^</level^> >> "%INSTALL_DIR%\config.xml"
echo         ^<console^>true^</console^> >> "%INSTALL_DIR%\config.xml"
echo     ^</logger^> >> "%INSTALL_DIR%\config.xml"
echo     ^<http_port^>8123^</http_port^> >> "%INSTALL_DIR%\config.xml"
echo     ^<tcp_port^>9000^</tcp_port^> >> "%INSTALL_DIR%\config.xml"
echo     ^<path^>%INSTALL_DIR%\data\^</path^> >> "%INSTALL_DIR%\config.xml"
echo     ^<tmp_path^>%INSTALL_DIR%\tmp\^</tmp_path^> >> "%INSTALL_DIR%\config.xml"
echo     ^<user_files_path^>%INSTALL_DIR%\user_files\^</user_files_path^> >> "%INSTALL_DIR%\config.xml"
echo     ^<format_schema_path^>%INSTALL_DIR%\format_schemas\^</format_schema_path^> >> "%INSTALL_DIR%\config.xml"
echo ^</clickhouse^> >> "%INSTALL_DIR%\config.xml"

REM Create data directories
if not exist "%INSTALL_DIR%\data" mkdir "%INSTALL_DIR%\data"
if not exist "%INSTALL_DIR%\tmp" mkdir "%INSTALL_DIR%\tmp"
if not exist "%INSTALL_DIR%\user_files" mkdir "%INSTALL_DIR%\user_files"
if not exist "%INSTALL_DIR%\format_schemas" mkdir "%INSTALL_DIR%\format_schemas"

echo Configuration files created successfully!
echo.

echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo ClickHouse installed to: %INSTALL_DIR%
echo.
echo To start ClickHouse server:
echo   cd %INSTALL_DIR%
echo   clickhouse.exe server
echo.
echo To use ClickHouse client:
echo   cd %INSTALL_DIR%
echo   clickhouse.exe client
echo.
echo HTTP endpoint: http://localhost:8123
echo TCP endpoint: localhost:9000
echo.
echo Default credentials:
echo   Username: default
echo   Password: (empty)
echo.

pause
