$ErrorActionPreference = "Stop"
$backendDir = "D:\my progect\估二手\backend"
$frontendDir = "D:\my progect\估二手\frontend"

# Kill any existing processes
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*main.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Start backend
Write-Host "[START] Backend..."
$backendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; python main.py" -PassThru -WindowStyle Normal
Start-Sleep -Seconds 3

# Start frontend
Write-Host "[START] Frontend..."
$frontendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendDir'; npm run dev" -PassThru -WindowStyle Normal

Write-Host "Backend PID: $($backendProc.Id)"
Write-Host "Frontend PID: $($frontendProc.Id)"

# Save PIDs
"Backend PID: $($backendProc.Id)" | Out-File -FilePath "D:\my progect\估二手\_startup_pids.txt" -Encoding utf8
"Frontend PID: $($frontendProc.Id)" | Out-File -FilePath "D:\my progect\估二手\_startup_pids.txt" -Append -Encoding utf8

Write-Host "[DONE] Both servers started!"
