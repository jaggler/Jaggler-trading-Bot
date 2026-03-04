@echo off
:: Change directory to your project folder
cd /d "C:\Users\WILFRED KIMATHI\Downloads\jules_session_3710676403765313323\forex_ml_trader"

:: Activate the virtual environment
call trading_env\Scripts\activate

:: Run the bot
python main.py

:: Optional: Keep window open if it fails so you can see why
if %errorlevel% neq 0 pause