@echo off
echo SRCC チャットボット 起動中...

:: バックエンド（uvicorn）を別ウィンドウで起動
start "SRCC Backend" cmd /k "cd /d C:\Users\hashiguchi\ClaudeProjects\srcc-faq-bot && uvicorn app.main:app --reload"

:: 少し待ってからフロントエンド（Next.js）を別ウィンドウで起動
timeout /t 3 /nobreak > nul
start "SRCC Frontend" cmd /k "cd /d C:\Users\hashiguchi\ClaudeProjects\srcc-faq-bot\frontend && npm run dev"

:: ブラウザを開く（さらに少し待ってから）
timeout /t 5 /nobreak > nul
start http://localhost:3000

echo 起動完了。ブラウザが開きます。
