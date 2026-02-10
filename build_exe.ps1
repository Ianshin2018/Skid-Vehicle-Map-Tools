# MapPlot 打包腳本
# 使用 PyInstaller 將 Python 專案打包成 Windows 執行檔

Write-Host "開始打包 MapPlot..." -ForegroundColor Green

# 清理舊的建置檔案
if (Test-Path "dist") {
    Write-Host "清理舊的 dist 目錄..." -ForegroundColor Yellow
    Remove-Item -Path "dist" -Recurse -Force
}
if (Test-Path "build") {
    Write-Host "清理舊的 build 目錄..." -ForegroundColor Yellow
    Remove-Item -Path "build" -Recurse -Force
}

# 執行 PyInstaller
Write-Host "執行 PyInstaller..." -ForegroundColor Yellow
.\.venv\Scripts\pyinstaller.exe `
    --name MapPlot `
    --onefile `
    --noconsole `
    --icon=icon.ico `
    main.py

# 檢查打包結果
if (Test-Path "dist\MapPlot.exe") {
    Write-Host "`n✓ 打包成功!" -ForegroundColor Green
    $exe = Get-Item "dist\MapPlot.exe"
    Write-Host "執行檔位置: $($exe.FullName)" -ForegroundColor Cyan
    Write-Host "檔案大小: $([math]::Round($exe.Length / 1MB, 2)) MB" -ForegroundColor Cyan
    Write-Host "建立時間: $($exe.LastWriteTime)" -ForegroundColor Cyan
} else {
    Write-Host "`n✗ 打包失敗" -ForegroundColor Red
    exit 1
}

Write-Host "`n注意: 執行檔位於 dist\MapPlot.exe" -ForegroundColor Green
