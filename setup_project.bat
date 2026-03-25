@echo off
echo ========================================
echo  Dual Drone Crowd Flow Simulation Setup
echo ========================================
echo.

echo Step 1: Installing Python dependencies...
cd dual-drone-simulation\backend
pip install -r requirements.txt
echo.

echo Step 2: Installing Node.js dependencies...
cd ..\frontend
npm install
echo.

echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo To run the simulation:
echo.
echo Terminal 1 (Backend):
echo   cd dual-drone-simulation\backend
echo   python sim_server.py
echo.
echo Terminal 2 (Frontend):
echo   cd dual-drone-simulation\frontend
echo   npm run dev
echo.
echo Then open http://localhost:3000 in your browser.
echo ========================================
pause
