# Stevo Discord Join Scraper (Option C — one worker per brand)

Self-bot join tracker for **klentozz** — forwards captures to the **Stevo Auto Wise**
group chat. It subscribes to member-join events on every server the account is in
and forwards a **NEW MEMBER CAPTURED** card to one group chat.

## Folder layout

```
scraper-stevo/
├── bot/
│   ├── bot.py            # the actual bot (run this)
│   ├── requirements.txt
│   └── .env.example
├── scripts/new-customer.sh
├── templates/render-env.example
├── bot.py                # launcher (runs bot/bot.py from repo root)
├── requirements.txt      # -r bot/requirements.txt
├── .env                  # USER_TOKEN + CHAT_ID (never commit)
├── .gitignore
└── README.md
```

## How it captures

1. **Gateway joins** — on startup it calls `guild.subscribe(member_updates=True)`
   on every server (requires `discord.py-self>=2.1`), so `on_member_join` fires
   for live joins newer than `JOIN_MAX_AGE_SECONDS` (default 600s).
2. **Join system messages** — Discord's native "X joined" messages in a welcome
   channel the account can read.
3. **Log-bot / welcome-bot posts** — "New Member Joined!" cards or "Welcome @user"
   greetings.

## Local run

```powershell
cd C:\Users\HP\Downloads\scraper-stevo
pip install -r requirements.txt
python bot.py
```

Run **one** instance per token (local **or** Render, never both).

## Render (Background Worker)

- **Root Directory:** `bot`
- **Build:** `pip install -r requirements.txt`
- **Start:** `python bot.py`
- **Env:** `USER_TOKEN` (secret) + `CHAT_ID` + `CLIENT_NAME=Stevo` + `PYTHON_VERSION=3.11.9`

Self-botting violates Discord ToS; use at your own risk.
