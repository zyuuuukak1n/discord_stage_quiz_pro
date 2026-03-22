import asyncio
import os
from dotenv import load_dotenv
import uvicorn

# .envファイルから環境変数を読み込む
load_dotenv()

from src.main import app
from src.bot import start_bot

async def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("環境変数 DISCORD_BOT_TOKEN が設定されていません。.env ファイルを確認してください。")

    # FastAPIを起動するためのUvicorn設定
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    
    # FastAPIサーバーとDiscord Botを並行して実行
    print("Starting FastAPI on port 8000 and Discord Bot...")
    await asyncio.gather(
        server.serve(),
        start_bot(token)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
