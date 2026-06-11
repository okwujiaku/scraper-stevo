"""
Self-bot join scraper — self-detecting "Smart Tech" + forwarder in one account.

Two capture paths, both forwarding a NEW MEMBER CAPTURED card to one group chat:
  1. Live joins: subscribes to member_updates on every server the account is in
     (discord.py-self requires guild.subscribe(member_updates=True) for
     on_member_join to fire) and reports genuinely new joins.
  2. Log-bot posts: on_message reader for "New Member Joined!" cards (kept so an
     external feed still works if one exists).

Set DISCORD_TOKEN / USER_TOKEN + CHAT_ID (or TOKEN_CLIENT_N / CHAT_ID_CLIENT_N
with CLIENT_INDEX) in .env or on Render. CLIENT_NAME sets the label.

WARNING: Automating a user account (self-botting) violates Discord's ToS.
"""

import asyncio
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

import discord
from dotenv import load_dotenv

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


def _load_env() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(here, ".env"),
        os.path.join(os.path.dirname(here), ".env"),
    ):
        if os.path.isfile(candidate):
            load_dotenv(candidate)
            return
    load_dotenv()


_load_env()


def _client_index() -> int:
    raw = (os.getenv("CLIENT_INDEX") or "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _load_credentials(index: int) -> tuple[str, int, str]:
    token = (
        (os.getenv("USER_TOKEN") or os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN") or "")
        .strip()
        or (os.getenv(f"TOKEN_CLIENT_{index}") or "").strip()
    )
    chat_raw = (
        (os.getenv(f"CHAT_ID_CLIENT_{index}") or "").strip()
        or (os.getenv("CHAT_ID") or "").strip()
        or (os.getenv("CHAT_ID_CLIENT_1") or "").strip()
        or "0"
    )
    label = (
        (os.getenv("CLIENT_NAME") or os.getenv(f"NAME_CLIENT_{index}") or "")
        .strip()
        or f"Client {index}"
    )
    return token, int(chat_raw or 0), label


CLIENT_INDEX = _client_index()
TOKEN, CHAT_ID, CLIENT_NAME = _load_credentials(CLIENT_INDEX)

DEBUG_INCOMING = (os.getenv("DEBUG_INCOMING") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
DISPLAY_TIMEZONE = (os.getenv("DISPLAY_TIMEZONE") or os.getenv("TZ") or "").strip()
try:
    JOIN_MAX_AGE_SECONDS = max(
        60, int((os.getenv("JOIN_MAX_AGE_SECONDS") or "600").strip() or "600")
    )
except ValueError:
    JOIN_MAX_AGE_SECONDS = 600

FIELD_STYLE = [
    ("Date", "date", "📅", C.CYAN),
    ("Time", "time", "⏰", C.CYAN),
    ("Username", "username", "👤", C.GREEN),
    ("Target Server", "server_name", "🏠", C.PURPLE),
]


def _card_time(when: datetime | None = None) -> tuple[str, str]:
    instant = when or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    if DISPLAY_TIMEZONE and ZoneInfo is not None:
        try:
            local = instant.astimezone(ZoneInfo(DISPLAY_TIMEZONE))
        except Exception:
            local = instant.astimezone()
    else:
        local = instant.astimezone()
    time_str = local.strftime("%I:%M:%S %p")
    if time_str.startswith("0"):
        time_str = time_str[1:]
    date_str = f"{local.strftime('%B')} {local.day}, {local.strftime('%Y')}"
    return date_str, time_str


def process_extracted_data(data: dict) -> None:
    rows = [
        (label, icon, color, data.get(key) or "N/A")
        for label, key, icon, color in FIELD_STYLE
    ]

    title = "✨ NEW MEMBER CAPTURED ✨"
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
    print(f"[{CLIENT_NAME}] capture detected", flush=True)
    try:
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
    except UnicodeEncodeError:
        for label, key, _, _ in FIELD_STYLE:
            print(f"  {label}: {data.get(key) or 'N/A'}", flush=True)
    print()


def build_message(data: dict) -> str:
    card = [
        "🎉 **NEW MEMBER CAPTURED** 🎉",
        f"📅 **Date:** {data.get('date') or 'N/A'}",
        f"⏰ **Time:** {data.get('time') or 'N/A'}",
        f"👤 **Username:** `{data.get('username') or 'N/A'}`",
        f"🆔 **User ID:** {data.get('user_id') or 'N/A'}",
        f"🏠 **Target Server:** {data.get('server_name') or 'N/A'}",
    ]
    return "\n".join(card) + "\n\u200b\n" + "─" * 30


def collect_message_text(message: discord.Message) -> str:
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


def is_join_log(text: str) -> bool:
    lowered = text.lower()
    return (
        "username:" in lowered
        and "user id:" in lowered
        and ("new member joined" in lowered or "member joined!" in lowered)
    )


def parse_join_log(full_text: str) -> dict | None:
    if not is_join_log(full_text):
        return None

    def clean(match):
        if not match:
            return None
        return match.group(1).strip().replace("**", "").replace("`", "").strip()

    server = clean(
        re.search(r"Target\s+Server:\s*(.+)", full_text, re.IGNORECASE)
    ) or clean(re.search(r"Server:\s*(.+)", full_text, re.IGNORECASE))

    return {
        "date": clean(re.search(r"Date:\s*(.+)", full_text, re.IGNORECASE)),
        "time": clean(re.search(r"Time:\s*(.+)", full_text, re.IGNORECASE)),
        "username": clean(re.search(r"Username:\s*(.+)", full_text, re.IGNORECASE)),
        "server_name": server,
        "user_id": clean(re.search(r"User ID:\s*(.+)", full_text, re.IGNORECASE)),
    }


def build_join_data(member: discord.Member) -> dict:
    joined_at = getattr(member, "joined_at", None)
    date_str, time_str = _card_time(joined_at)
    guild = getattr(member, "guild", None)
    return {
        "date": date_str,
        "time": time_str,
        "username": member.name or "N/A",
        "user_id": str(member.id),
        "server_name": guild.name if guild else "N/A",
    }


def build_capture_from_user(
    user: discord.abc.User,
    guild: discord.Guild | None,
    when: datetime | None = None,
) -> dict:
    date_str, time_str = _card_time(when)
    return {
        "date": date_str,
        "time": time_str,
        "username": getattr(user, "name", None) or "N/A",
        "user_id": str(getattr(user, "id", "")),
        "server_name": guild.name if guild else "N/A",
    }


def parse_welcome_bot_message(message: discord.Message) -> dict | None:
    """A welcome bot (MEE6, etc.) greeting a newly joined, mentioned user."""
    if message.guild is None or not message.author.bot or not message.mentions:
        return None
    text = collect_message_text(message).lower()
    if not any(k in text for k in ("welcome", "just joined", "new member", "joined the")):
        return None
    user = next((m for m in message.mentions if not getattr(m, "bot", False)), None)
    if user is None:
        return None
    return build_capture_from_user(user, message.guild, message.created_at)


class ScraperClient(discord.Client):
    def __init__(self, target_chat_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_chat_id = target_chat_id
        self._target_channel = None
        self._recent: dict[tuple[str, str], float] = {}

    async def _open_channel(self) -> None:
        if not self.target_chat_id:
            print(
                f"[{CLIENT_NAME}] No target chat ID configured; will capture but not forward.",
                flush=True,
            )
            return
        try:
            self._target_channel = await self.fetch_channel(self.target_chat_id)
            print(
                f"[{CLIENT_NAME}] Forwarding captures to: {self._target_channel} "
                f"(id: {self.target_chat_id})",
                flush=True,
            )
        except Exception as exc:
            print(
                f"[{CLIENT_NAME}] Could not open chat {self.target_chat_id}: {exc}",
                flush=True,
            )

    async def _subscribe_member_events(self) -> None:
        """Best-effort: enable gateway on_member_join where the library supports it.

        discord.py-self >= 2.1 exposes Guild.subscribe(member_updates=True). On
        2.0.0 it doesn't exist, so we silently skip and rely on on_message join
        detection (native "X joined" system messages + welcome-bot posts).
        """
        if not hasattr(discord.Guild, "subscribe"):
            print(
                f"[{CLIENT_NAME}] Gateway member-events unavailable on this "
                "discord.py-self version; using message-based join detection.",
                flush=True,
            )
            return
        ok = 0
        for guild in self.guilds:
            try:
                await guild.subscribe(typing=True, member_updates=True)
                ok += 1
            except Exception as exc:
                if DEBUG_INCOMING:
                    print(
                        f"[{CLIENT_NAME}] subscribe failed for {guild.name}: {exc}",
                        flush=True,
                    )
            await asyncio.sleep(0.3)
        print(
            f"[{CLIENT_NAME}] Subscribed to member-join events on "
            f"{ok}/{len(self.guilds)} server(s).",
            flush=True,
        )

    async def _forward(self, data: dict, source: str) -> None:
        key = (str(data.get("user_id") or ""), str(data.get("server_name") or "").lower())
        now = time.time()
        if key[0]:
            last = self._recent.get(key)
            if last and now - last < 120:
                return
            self._recent[key] = now

        try:
            process_extracted_data(data)
        except UnicodeEncodeError:
            print(f"[{CLIENT_NAME}] capture detected ({source}).", flush=True)

        channel = self._target_channel
        if channel is None:
            if not self.target_chat_id:
                return
            try:
                channel = await self.fetch_channel(self.target_chat_id)
                self._target_channel = channel
            except Exception as exc:
                print(f"[{CLIENT_NAME}] Target chat unavailable: {exc}", flush=True)
                return

        try:
            await channel.send(build_message(data))
            print(
                f"[{CLIENT_NAME}] Forwarded capture ({source}) for "
                f"{data.get('username') or 'unknown'} in {data.get('server_name')}.",
                flush=True,
            )
        except Exception as exc:
            print(f"[{CLIENT_NAME}] Send failed: {exc}", flush=True)

    async def on_ready(self):
        print(f"[{CLIENT_NAME}] Logged in as {self.user} (id: {self.user.id})", flush=True)
        await self._open_channel()

        guild_names = sorted(g.name for g in self.guilds)
        preview = ", ".join(guild_names[:10])
        if len(guild_names) > 10:
            preview += f", ... (+{len(guild_names) - 10} more)"
        print(
            f"[{CLIENT_NAME}] Watching {len(self.guilds)} server(s): {preview}",
            flush=True,
        )

        await self._subscribe_member_events()
        print(
            f"[{CLIENT_NAME}] Live capture ON — detecting 'X joined' system "
            "messages, welcome-bot greetings, and log-bot 'New Member Joined!' posts.",
            flush=True,
        )

    async def on_member_join(self, member: discord.Member):
        guild = getattr(member, "guild", None)
        if guild is None:
            return

        joined_at = getattr(member, "joined_at", None) or datetime.now(timezone.utc)
        if joined_at.tzinfo is None:
            joined_at = joined_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - joined_at).total_seconds()

        if DEBUG_INCOMING:
            print(
                f"[{CLIENT_NAME}] JOIN event: {member.name} in {guild.name} "
                f"| age={int(age)}s",
                flush=True,
            )

        if age > JOIN_MAX_AGE_SECONDS:
            return

        await self._forward(build_join_data(member), "gateway")

    async def on_message(self, message: discord.Message):
        text = collect_message_text(message)
        is_member_join_msg = message.type == discord.MessageType.member_join

        if DEBUG_INCOMING:
            channel_label = getattr(message.channel, "name", str(message.channel))
            guild_label = message.guild.name if message.guild else "DM"
            snippet = " ".join(text.split())[:160]
            kind = "JOIN-SYS" if is_member_join_msg else f"match={is_join_log(text)}"
            print(
                f"[{CLIENT_NAME}] SEEN [{guild_label} #{channel_label}] "
                f"from {message.author} | {kind} | {snippet}",
                flush=True,
            )

        if self.user and message.author.id == self.user.id:
            return

        source = None
        data = parse_join_log(text)
        if data is not None:
            source = "log-bot"
        elif is_member_join_msg and message.guild is not None:
            data = build_capture_from_user(
                message.author, message.guild, message.created_at
            )
            source = "join-message"
        else:
            data = parse_welcome_bot_message(message)
            if data is not None:
                source = "welcome-bot"

        if data is None:
            return
        await self._forward(data, source)


async def main():
    if not TOKEN:
        raise SystemExit(
            "No token set. Use DISCORD_TOKEN, USER_TOKEN, or TOKEN_CLIENT_N on this worker."
        )
    if not CHAT_ID:
        raise SystemExit(
            "No chat ID set. Use CHAT_ID, CHAT_ID_CLIENT_N, or CHAT_ID_CLIENT_1 on this worker."
        )

    print(
        f"[{CLIENT_NAME}] Starting scraper (Option C, chat id {CHAT_ID})...",
        flush=True,
    )
    client = ScraperClient(target_chat_id=CHAT_ID, chunk_guilds_at_startup=False)
    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
