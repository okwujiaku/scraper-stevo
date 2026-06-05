"""
Stevo join tracker — terminal + optional group-chat forward (self-bot).

Universal capture: Discord's on_member_join fires for every server you are in,
regardless of log-bot message format.

Optional CAPTURE_MODE=all also scans bot/welcome messages for extra log-bot hits.
Set CHAT_ID to forward visible captures to a group DM (e.g. Stevo Auto Wise).

WARNING: Automating a user account (self-botting) violates Discord's ToS.
"""

import asyncio
import os
import re
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import discord
from dotenv import load_dotenv

USER_TOKEN = ""

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

try:
    _orig_parse_ready_supplemental = (
        discord.state.ConnectionState.parse_ready_supplemental
    )

    def _safe_parse_ready_supplemental(self, extra_data, *args, **kwargs):
        ready = getattr(self, "_ready_data", None)
        if isinstance(ready, dict) and ready.get("pending_payments") is None:
            ready["pending_payments"] = []
        return _orig_parse_ready_supplemental(self, extra_data, *args, **kwargs)

    discord.state.ConnectionState.parse_ready_supplemental = (
        _safe_parse_ready_supplemental
    )
except Exception:
    pass

_FALLBACK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
)
try:
    from discord import utils as _discord_utils

    _orig_get_user_agent = _discord_utils._get_user_agent

    async def _get_user_agent_safe(session):
        try:
            return await _orig_get_user_agent(session)
        except Exception:
            print(
                "[Stevo] User-agent fetch failed (network/DNS); using fallback.",
                flush=True,
            )
            return _FALLBACK_USER_AGENT

    _discord_utils._get_user_agent = _get_user_agent_safe

    _orig_get_build_number = _discord_utils._get_build_number

    async def _get_build_number_safe(session):
        try:
            return await _orig_get_build_number(session)
        except Exception:
            print(
                "[Stevo] Build number fetch failed (network/DNS); using fallback.",
                flush=True,
            )
            return 9999

    _discord_utils._get_build_number = _get_build_number_safe
except Exception:
    pass


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GOLD = "\033[38;5;220m"
    CYAN = "\033[38;5;51m"
    GREEN = "\033[38;5;48m"
    PINK = "\033[38;5;213m"
    PURPLE = "\033[38;5;141m"
    GRAY = "\033[38;5;245m"
    WHITE = "\033[97m"


_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    load_dotenv(_env_path)

_env_token = (
    os.getenv("USER_TOKEN")
    or os.getenv("DISCORD_TOKEN")
    or os.getenv("TOKEN")
    or ""
).strip()
if _env_token:
    USER_TOKEN = _env_token

CLIENT_NAME = (os.getenv("CLIENT_NAME") or "Stevo").strip()
CHAT_ID = (
    os.getenv("CHAT_ID")
    or os.getenv("FORWARD_CHAT_ID")
    or ""
).strip()
# all = guild joins + welcome/log bots (recommended). guild = joins only.
CAPTURE_MODE = (os.getenv("CAPTURE_MODE") or "all").strip().lower()
DEBUG = (os.getenv("DEBUG") or "").strip().lower() in ("1", "true", "yes", "on")
SEND_STARTUP_PING = (os.getenv("SEND_STARTUP_PING") or "true").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
TEST_CAPTURE = (os.getenv("TEST_CAPTURE") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# Comma-separated server names: guild-join captures still run (dedupe, events) but no terminal box.
HIDE_GUILD_JOIN_SERVERS = frozenset(
    s.strip().lower()
    for s in (os.getenv("HIDE_GUILD_JOIN_SERVERS") or "").split(",")
    if s.strip()
)
# Skip log-bot capture when guild join already covers these servers (avoids Cryptera doubles).
SKIP_LOG_IF_GUILD_JOIN = frozenset(
    s.strip().lower()
    for s in (os.getenv("SKIP_LOG_IF_GUILD_JOIN") or "Cryptera").split(",")
    if s.strip()
)
DISPLAY_TIMEZONE = (
    os.getenv("DISPLAY_TIMEZONE") or os.getenv("TZ") or ""
).strip()

JOIN_CHANNEL_HINTS = (
    "welcome",
    "join",
    "log",
    "rules",
    "general",
    "chat",
    "lobby",
    "entrance",
)

JOIN_TEXT_HINTS = (
    "joined",
    "welcome",
    "new member",
    "member join",
    "user join",
)


FIELD_STYLE = [
    ("Date", "date", "📅", C.CYAN),
    ("Time", "time", "⏰", C.CYAN),
    ("Username", "username", "👤", C.GREEN),
    ("User ID", "user_id", "🆔", C.PURPLE),
    ("Target Server", "server_name", "🏠", C.PURPLE),
]

CAPTURE_TITLE = "😊 New member joined"


def _normalize_dt(dt: datetime | None = None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _local_parts_from_dt(dt: datetime | None = None) -> tuple[str, str]:
    instant = _normalize_dt(dt)
    if DISPLAY_TIMEZONE:
        try:
            local = instant.astimezone(ZoneInfo(DISPLAY_TIMEZONE))
        except Exception:
            local = instant.astimezone()
    else:
        local = instant.astimezone()
    time_str = local.strftime("%I:%M %p")
    if time_str.startswith("0"):
        time_str = time_str[1:]
    try:
        day = local.strftime("%#d")
    except ValueError:
        day = str(local.day)
    date_str = f"{local.strftime('%B')} {day}, {local.strftime('%Y')}"
    return date_str, time_str


def _capture_time_fields(when: datetime | None = None) -> dict:
    """captured_at = unix instant; date/time strings for plain-text group messages."""
    instant = _normalize_dt(when)
    date, time_str = _local_parts_from_dt(instant)
    return {
        "captured_at": int(instant.timestamp()),
        "date": date,
        "time": time_str,
    }


def process_extracted_data(data: dict) -> None:
    rows = [
        (label, icon, color, data.get(key) or "N/A")
        for label, key, icon, color in FIELD_STYLE
    ]

    title = CAPTURE_TITLE
    title_cells = len(title) + 2
    label_width = max(len(label) for label, *_ in rows)
    inner_width = max(
        title_cells,
        max(3 + label_width + 3 + len(str(value)) for *_, value in rows),
    )

    top = f"{C.GOLD}╔{'═' * (inner_width + 2)}╗{C.RESET}"
    sep = f"{C.GOLD}╠{'═' * (inner_width + 2)}╣{C.RESET}"
    bot_line = f"{C.GOLD}╚{'═' * (inner_width + 2)}╝{C.RESET}"
    bar = f"{C.GOLD}║{C.RESET}"
    title_pad = inner_width - title_cells
    left = title_pad // 2
    right = title_pad - left

    print()
    source = data.get("source") or "capture"
    print(f"[{CLIENT_NAME}] capture detected ({source})", flush=True)
    print(top)
    print(f"{bar} {' ' * left}{C.BOLD}{C.PINK}{title}{C.RESET}{' ' * right} {bar}")
    print(sep)
    for label, icon, color, value in rows:
        plain_len = 3 + label_width + 3 + len(str(value))
        pad = " " * (inner_width - plain_len)
        print(
            f"{bar} {icon} {color}{label:<{label_width}}{C.RESET}"
            f"{C.GRAY} : {C.RESET}{C.WHITE}{value}{C.RESET}{pad} {bar}"
        )
    print(bot_line)
    print()


def format_capture_message(data: dict) -> str:
    """Plain text for group DM — self-bots cannot use embeds."""
    lines = [f"**{CAPTURE_TITLE}**"]
    for label, key, icon, _ in FIELD_STYLE:
        value = str(data.get(key) or "N/A")
        if key == "username":
            value = f"`{value}`"
        lines.append(f"{icon} **{label}:** {value}")
    lines.extend(["", "─" * 28])
    return "\n".join(lines)


def build_full_text(message: discord.Message) -> str:
    parts = [message.content or ""]
    for embed in message.embeds:
        parts.append(embed.title or "")
        parts.append(embed.description or "")
        if embed.author:
            parts.append(embed.author.name or "")
        if embed.footer:
            parts.append(embed.footer.text or "")
        for field in embed.fields:
            name = (field.name or "").strip()
            value = (field.value or "").strip()
            if name and value:
                parts.append(f"{name}: {value}")
            else:
                parts.append(name)
                parts.append(value)
    return "\n".join(parts)


def _join_text_signal(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in JOIN_TEXT_HINTS)


def _join_channel(channel_name: str) -> bool:
    lowered = channel_name.lower()
    return any(hint in lowered for hint in JOIN_CHANNEL_HINTS)


def _snowflake_from_text(text: str) -> str | None:
    match = re.search(r"<@!?(\d{17,20})>", text)
    if match:
        return match.group(1)
    for match in re.finditer(r"\b(\d{17,20})\b", text):
        return match.group(1)
    return None


def _mention_user(message: discord.Message) -> tuple[str | None, str | None]:
    candidates = [m for m in message.mentions if m.id != message.author.id]
    if not candidates:
        candidates = list(message.mentions)
    if not candidates:
        return None, None
    user = candidates[0]
    return getattr(user, "name", None) or str(user), str(user.id)


def _regex_field(full_text: str, label: str) -> str | None:
    match = re.search(rf"{label}\s*:\s*(.+)", full_text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip().replace("**", "").replace("`", "").strip()


def capture_from_member(member: discord.Member) -> dict:
    guild = member.guild.name if member.guild else "N/A"
    return {
        **_capture_time_fields(),
        "username": member.name or "N/A",
        "user_id": str(member.id),
        "server_name": guild,
        "source": f"guild join · {guild}",
    }


def extract_join_from_message(message: discord.Message) -> dict | None:
    """
    Best-effort log-bot parser (any format): mentions, embeds, labels, or IDs in text.
    Cannot parse messages with zero user info (e.g. plain 'welcome' with no @user).
    """
    if not message.guild:
        return None

    full_text = build_full_text(message)
    channel = getattr(message.channel, "name", "") or ""
    guild = message.guild.name
    is_bot = getattr(message.author, "bot", False)
    joinish = _join_text_signal(full_text) or _join_channel(channel)

    username, user_id = _mention_user(message)

    if not user_id:
        user_id = _snowflake_from_text(full_text)

    for embed in message.embeds:
        for chunk in (
            embed.title,
            embed.description,
            embed.footer.text if embed.footer else None,
        ):
            if chunk and not user_id:
                user_id = _snowflake_from_text(chunk)
        for field in embed.fields:
            blob = f"{field.name} {field.value}"
            if not user_id:
                user_id = _snowflake_from_text(blob)
            fname = (field.name or "").lower()
            fval = (field.value or "").strip()
            if not username and any(k in fname for k in ("user", "member", "name")):
                username = fval.lstrip("@").replace("**", "").replace("`", "")

    if not username:
        username = _regex_field(full_text, "Username") or _regex_field(
            full_text, "User"
        )

    if not user_id:
        user_id = _regex_field(full_text, "User ID") or _regex_field(
            full_text, "Discord ID"
        )
        if user_id:
            found = re.search(r"\d{17,20}", user_id)
            user_id = found.group(0) if found else user_id

    if not user_id:
        return None

    # Universal welcome bots: @mention in a bot message = join (any channel).
    bot_welcome = is_bot and bool(message.mentions)
    if not (joinish or bot_welcome or (is_bot and _join_channel(channel))):
        return None

    # Prefer embed "Target Server" — log bots often name the real server.
    target = (
        _regex_field(full_text, "Target Server")
        or _regex_field(full_text, "Server")
        or _regex_field(full_text, "Guild")
    )
    server = target or guild

    source = f"log message · {server}"
    if guild != server:
        source += f" (posted in {guild}"
        if channel:
            source += f" / #{channel}"
        source += ")"
    elif channel:
        source += f" / #{channel}"

    return {
        **_capture_time_fields(message.created_at),
        "username": username or "N/A",
        "user_id": str(user_id),
        "server_name": server,
        "source": source,
    }


class ScraperClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._recent_captures: dict[tuple[str, str], float] = {}
        self._servers_seen: set[str] = set()
        self._forward_channel: discord.abc.Messageable | None = None
        self._ready_once = False
        self._capture_lock = asyncio.Lock()

    @staticmethod
    def _is_quiet_guild_join(data: dict) -> bool:
        source = str(data.get("source") or "")
        if not source.startswith("guild join · "):
            return False
        server = str(data.get("server_name") or "").strip().lower()
        return server in HIDE_GUILD_JOIN_SERVERS

    async def _open_forward_channel(self) -> None:
        self._forward_channel = None
        if not CHAT_ID:
            print(
                f"[{CLIENT_NAME}] No CHAT_ID set — terminal only.",
                flush=True,
            )
            return
        try:
            channel_id = int(CHAT_ID)
        except ValueError:
            print(f"[{CLIENT_NAME}] Invalid CHAT_ID: {CHAT_ID!r}", flush=True)
            return
        try:
            channel = self.get_channel(channel_id)
            if channel is None:
                channel = await self.fetch_channel(channel_id)
            self._forward_channel = channel
            label = getattr(channel, "name", None) or str(channel)
            print(
                f"[{CLIENT_NAME}] Forwarding captures to: {label} (id: {channel_id})",
                flush=True,
            )
        except Exception as exc:
            print(
                f"[{CLIENT_NAME}] Could not open chat {CHAT_ID}: {exc}",
                flush=True,
            )

    async def _send_to_group(self, content: str) -> bool:
        if not self._forward_channel:
            return False
        try:
            await self._forward_channel.send(content)
            return True
        except Exception as exc:
            print(f"[{CLIENT_NAME}] Forward failed: {exc}", flush=True)
            return False

    async def _forward_capture(self, data: dict) -> None:
        if await self._send_to_group(format_capture_message(data)):
            print(f"[{CLIENT_NAME}] Sent to group chat.", flush=True)

    async def _send_startup_ping(self) -> None:
        if not SEND_STARTUP_PING or not self._forward_channel:
            return
        n = len(self.guilds)
        text = (
            f"🟢 **{CLIENT_NAME}** online — tracking **{n}** server(s).\n"
            "_scraper-stevo · one message per join_"
        )
        if await self._send_to_group(text):
            print(f"[{CLIENT_NAME}] Startup ping sent to group chat.", flush=True)

    async def _emit_capture(self, data: dict) -> None:
        user_id = str(data.get("user_id") or "")
        server = str(data.get("server_name") or "N/A").strip()
        key = (user_id, server.lower())
        now = time.time()

        async with self._capture_lock:
            if user_id and key in self._recent_captures:
                if now - self._recent_captures[key] < 90:
                    return
            if user_id:
                self._recent_captures[key] = now

        quiet = self._is_quiet_guild_join(data)
        if quiet:
            return

        self._servers_seen.add(server)
        process_extracted_data(data)
        if len(self._servers_seen) <= 12:
            seen = ", ".join(sorted(self._servers_seen))
        else:
            seen = ", ".join(sorted(list(self._servers_seen)[:8])) + f", ... (+{len(self._servers_seen) - 8})"
        print(f"[{CLIENT_NAME}] Servers seen this session ({len(self._servers_seen)}): {seen}", flush=True)
        await self._forward_capture(data)

    async def on_disconnect(self):
        print(
            f"[{CLIENT_NAME}] Disconnected — check Wi‑Fi/VPN/DNS. Reconnecting...",
            flush=True,
        )

    async def on_resumed(self):
        print(f"[{CLIENT_NAME}] Connection resumed.", flush=True)

    async def on_ready(self):
        print(f"[{CLIENT_NAME}] Logged in as {self.user} (id: {self.user.id})", flush=True)
        await self._open_forward_channel()
        print(
            f"[{CLIENT_NAME}] Tracking {len(self.guilds)} server(s) · mode={CAPTURE_MODE}"
            f" · tz={DISPLAY_TIMEZONE or 'system'}",
            flush=True,
        )
        guild_names = sorted(g.name for g in self.guilds)
        preview = ", ".join(guild_names[:10])
        if len(guild_names) > 10:
            preview += f", ... (+{len(guild_names) - 10} more)"
        print(f"[{CLIENT_NAME}] Servers: {preview}", flush=True)
        if CAPTURE_MODE == "guild":
            print(
                f"[{CLIENT_NAME}] Guild-join only. You will ONLY see servers where "
                "someone physically joins while you watch.\n",
                flush=True,
            )
        else:
            print(
                f"[{CLIENT_NAME}] Guild joins + welcome/log bots on all servers "
                "(bot @mentions, embeds, Target Server field).\n",
                flush=True,
            )

        if self._ready_once:
            return
        self._ready_once = True

        await self._send_startup_ping()
        print(
            f"[{CLIENT_NAME}] Waiting for joins — no output until someone joins "
            "or a log bot posts.",
            flush=True,
        )
        print(
            f"[{CLIENT_NAME}] IMPORTANT: run only THIS bot for klentozz. "
            "Stop Documents\\scraper and any Render worker on the same token "
            "or you will get duplicate group messages.\n",
            flush=True,
        )

        if TEST_CAPTURE:
            await asyncio.sleep(2)
            await self._emit_capture(
                {
                    **_capture_time_fields(),
                    "username": "test_user_local",
                    "user_id": "999000111222333444",
                    "server_name": "TEST SERVER (remove TEST_CAPTURE after verify)",
                    "source": "test capture · local verify",
                }
            )
            print(
                f"[{CLIENT_NAME}] TEST_CAPTURE done — set TEST_CAPTURE=false in .env "
                "for production.\n",
                flush=True,
            )

    async def on_member_join(self, member):
        await self._emit_capture(capture_from_member(member))

    async def on_message(self, message):
        if CAPTURE_MODE != "all":
            return
        if not message.guild or message.author.id == self.user.id:
            return

        data = extract_join_from_message(message)
        if data is None:
            if DEBUG and _join_text_signal(build_full_text(message)):
                ch = getattr(message.channel, "name", "?")
                print(
                    f"[{CLIENT_NAME}] DEBUG skip — no user in message "
                    f"({message.guild.name} / #{ch})",
                    flush=True,
                )
            return

        # Cryptera etc.: guild join + log bot would double; other servers need log-bot path.
        guild_name = message.guild.name
        server_name = str(data.get("server_name") or "").strip()
        if (
            server_name.lower() == guild_name.lower()
            and server_name.lower() in SKIP_LOG_IF_GUILD_JOIN
        ):
            return

        await self._emit_capture(data)


def _is_network_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return (
        "gaierror" in name.lower()
        or "ClientConnectorDNSError" in name
        or "getaddrinfo" in text
        or "cannot connect to host" in text
    )


async def main():
    if not USER_TOKEN:
        raise SystemExit(
            "No token set. Set USER_TOKEN in .env or at the top of bot.py."
        )

    print(f"[{CLIENT_NAME}] Starting terminal tracker...", flush=True)
    client = ScraperClient()

    for attempt in range(1, 6):
        try:
            await client.start(USER_TOKEN)
            return
        except KeyboardInterrupt:
            print(f"\n[{CLIENT_NAME}] Stopped.", flush=True)
            return
        except Exception as exc:
            if _is_network_error(exc) and attempt < 5:
                wait = 15 * attempt
                print(
                    f"[{CLIENT_NAME}] Network/DNS error (attempt {attempt}/5). "
                    f"Retrying in {wait}s...",
                    flush=True,
                )
                await asyncio.sleep(wait)
                continue
            raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Stevo] Stopped.", flush=True)
