# Stevo Discord Join Scraper (terminal only)

Self-bot join tracker for **all servers** your account is in. Prints captures to the terminal and forwards them to a **group DM** (e.g. Stevo Auto Wise).

## Capture modes

**Recommended** — guild joins plus welcome/log bots:

```env
CAPTURE_MODE=all
```

Uses Discord’s **`on_member_join`** for every server, plus best-effort parsing of welcome/log bot messages (mentions, embeds, `Target Server:` fields).

**Guild joins only:**

```env
CAPTURE_MODE=guild
```

Only physical joins via `on_member_join`. No log-message parsing.

## Optional: hide noisy guild joins

To suppress terminal + group output for specific servers (joins still dedupe internally):

```env
HIDE_GUILD_JOIN_SERVERS=Cryptera
```

Comma-separate multiple names. Leave empty to show all servers (default).

## “Servers seen this session (7)” — what it means

That number is **not** how many servers you monitor. On startup you see something like `Tracking 71 server(s)`.

**Servers seen** = servers that had at least one **visible** capture during this run. If only 7 names appear, the other ~64 simply had no joins (or only quiet/hidden guild joins) while the bot was online. More names appear as activity happens.

## Forward to group chat

Set `CHAT_ID` to your group DM channel ID (the number in the URL after `@me/`):

```env
CHAT_ID=1511486061941882930
```

On startup you should see:

```text
Forwarding captures to: Stevo Auto Wise (id: 1511486061941882930)
```

Each visible capture prints in the terminal first, then posts an embed to that group. Quiet guild joins (`HIDE_GUILD_JOIN_SERVERS`) are not forwarded.

Leave `CHAT_ID` empty for terminal-only mode.

## Local setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set USER_TOKEN and CHAT_ID
python bot.py
```

Self-botting violates Discord ToS; use at your own risk.

**Important:** Run only **one** instance per token (local **or** Render, not both at once).

---

## Deploy on Render (smooth 24/7)

Yes — push to GitHub first, then connect Render to that repo.

### 1. Push to GitHub

```bash
cd scraper-stevo
git init
git add bot.py requirements.txt README.md .env.example .gitignore render.yaml
git commit -m "Stevo terminal join tracker"
git branch -M main
git remote add origin https://github.com/YOUR_USER/scraper-stevo.git
git push -u origin main
```

Never commit `.env` (it is gitignored).

### 2. Create Render worker

1. [Render Dashboard](https://dashboard.render.com) → **New** → **Background Worker**
2. Connect your GitHub repo
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python bot.py`
5. **Environment variables** (Dashboard → Environment):

   | Key | Value |
   |-----|-------|
   | `USER_TOKEN` | your Discord user token |
   | `CHAT_ID` | `1511486061941882930` |
   | `CLIENT_NAME` | `Stevo` |
   | `CAPTURE_MODE` | `all` |
   | `DEBUG` | `false` |

6. Deploy. Logs appear under the worker’s **Logs** tab (same capture output as local).

Optional: use the included `render.yaml` blueprint (**New** → **Blueprint**) for one-click setup; still add `USER_TOKEN` manually in the dashboard.

### 3. Avoid disconnects

- Stop the local `python bot.py` before starting Render (same token = one session).
- Render’s network is usually more stable than home Wi‑Fi; the bot already retries DNS/gateway errors up to 5 times.

---

## Clone for a separate project

Each brand/instance should be its own repo and Render worker:

1. **GitHub:** Fork or duplicate the repo (e.g. `scraper-pikanto`), or `git clone` then `git remote set-url origin` to a new empty repo.
2. **Secrets:** New `.env` with a **different** `USER_TOKEN` (different Discord account) and `CLIENT_NAME` (e.g. `Pikanto`).
3. **Render:** New Background Worker pointing at the new repo; set env vars there (no shared `.env` between projects).
4. **Optional tweaks:** `HIDE_GUILD_JOIN_SERVERS`, `CAPTURE_MODE` per project.

Projects do not share code at runtime — only the same template if you copy the repo.
