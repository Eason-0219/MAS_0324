@echo off
chcp 65001 > nul
echo 正在關閉所有 MAS 服務...

taskkill /FI "WINDOWTITLE eq MCP Time*" /F > nul 2>&1
taskkill /FI "WINDOWTITLE eq MCP Weather*" /F > nul 2>&1
taskkill /FI "WINDOWTITLE eq MCP Search*" /F > nul 2>&1
taskkill /FI "WINDOWTITLE eq MAS Backend*" /F > nul 2>&1
taskkill /FI "WINDOWTITLE eq MAS Frontend*" /F > nul 2>&1

echo 完成。
pause
