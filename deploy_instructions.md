# Ubuntu Deployment Instructions

This guide covers how to deploy the Discord Stage Quiz App on an Ubuntu server, ensuring it runs persistently via `systemd`.

## 1. Prerequisites
- Ubuntu 20.04 or 22.04 server.
- Python 3.9+ installed (`sudo apt update && sudo apt install python3 python3-pip python3-venv ffmpeg`).
  - *Note: `ffmpeg` is required for PyNaCl and discord.py to play audio/sound effects.*

## 2. Setting Up the Environment
1. Clone the repository to `/opt/discord_stage_quiz_pro`.
   ```bash
   sudo git clone <your-repo-url> /opt/discord_stage_quiz_pro
   sudo chown -R $USER:$USER /opt/discord_stage_quiz_pro
   cd /opt/discord_stage_quiz_pro
   ```
2. Create and activate a virtual environment.
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies.
   ```bash
   pip install -r requirements.txt
   ```

## 3. Configuration & Startup Script
We need to run BOTH the FastAPI server and the Discord Bot. A Python script can be used to launch both in the same asyncio event loop, or we can use `uvicorn` and hook the bot into FastAPI's lifespan events.

Create `run.py` in the root directory:
```python
import asyncio
import os
import uvicorn
from src.main import app
from src.bot import start_bot

# Set up your BOT TOKEN as an environment variable or hardcode (not recommended)
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_TOKEN_HERE")

async def main():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uuvicorn.Server(config)
    
    # Run Uvicorn and Discord Bot concurrently
    await asyncio.gather(
        server.serve(),
        start_bot(BOT_TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(main())
```

## 4. Setting up `systemd` Daemon
Create a new service file:
```bash
sudo nano /etc/systemd/system/stagequiz.service
```

Add the following content (adjust paths and User as needed):
```ini
[Unit]
Description=Discord Stage Quiz Server
After=network.target

[Service]
User=root
# Set to the user who owns the files
WorkingDirectory=/opt/discord_stage_quiz_pro
Environment="PATH=/opt/discord_stage_quiz_pro/venv/bin"
Environment="DISCORD_BOT_TOKEN=your_actual_token_here"
ExecStart=/opt/discord_stage_quiz_pro/venv/bin/python run.py

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 5. Start and Enable Service
Reload systemd, start the service, and enable it to run on boot:
```bash
sudo systemctl daemon-reload
sudo systemctl start stagequiz
sudo systemctl enable stagequiz
```

## 6. Check Logs and Recoverability
Because state is stored in `sqlite:///./quiz.db`, if the server restarts or the process crashes, `systemd` will automatically restart it. Fast API immediately queries `GameState.id == 1` to recover where it left off.
Check logs with:
```bash
sudo journalctl -u stagequiz -f
```
