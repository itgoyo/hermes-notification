"""
hermes-notification plugin
==========================
Sends a system notification (banner + sound) every time Hermes
finishes a response. Useful when you're multitasking and want to know
the moment the AI is done — no need to keep checking the window.

Supported platforms
-------------------
- macOS  : native banner via osascript + sound via afplay
- Linux  : native banner via notify-send + sound via paplay/pw-play/aplay
- Windows: native banner via PowerShell + sound via PowerShell MediaPlayer

Config (optional) — create this file to override defaults:
~/.hermes/plugins/hermes-notification/config.json
{
    "sound": "Glass",          // macOS: name from /System/Library/Sounds/ (no .aiff)
                               // Linux: path to .wav/.oga file, or "" to disable
                               // Windows: "SystemAsterisk" / "SystemExclamation" / "" to disable
    "title": "Hermes ✅",      // notification title
    "preview_length": 100,     // chars of response shown in body (0 = no preview)
    "min_response_length": 10, // skip notifications for very short replies
    "enabled": true
}
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

DEFAULTS: dict = {
    "sound": "Glass",
    "title": "Hermes ✅",
    "preview_length": 100,
    "min_response_length": 10,
    "enabled": True,
}

_config: dict = {}

PLUGIN_DIR = Path.home() / ".hermes" / "plugins" / "hermes-notification"


def _load_config() -> dict:
    """Load config from plugin directory, falling back to defaults."""
    cfg = dict(DEFAULTS)
    config_path = PLUGIN_DIR / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg.update(json.load(f))
        except Exception as e:
            logger.warning("hermes-notification: failed to load config: %s", e)
    return cfg


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def _current_platform() -> str:
    """Return 'macos', 'linux', or 'windows'."""
    s = platform.system()
    if s == "Darwin":
        return "macos"
    if s == "Windows":
        return "windows"
    # WSL counts as linux here; afplay won't exist but notify-send will
    return "linux"


# ---------------------------------------------------------------------------
# macOS helpers
# ---------------------------------------------------------------------------

def _macos_notify(title: str, message: str) -> None:
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_message}" with title "{safe_title}"'
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception as e:
        logger.debug("hermes-notification: osascript failed: %s", e)


def _macos_sound(sound_name: str) -> None:
    if not sound_name:
        return
    path = (
        sound_name
        if ("/" in sound_name or sound_name.endswith(".aiff"))
        else f"/System/Library/Sounds/{sound_name}.aiff"
    )
    if not os.path.exists(path):
        logger.debug("hermes-notification: sound not found: %s", path)
        return
    try:
        subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.debug("hermes-notification: afplay failed: %s", e)


# ---------------------------------------------------------------------------
# Linux helpers
# ---------------------------------------------------------------------------

def _linux_notify(title: str, message: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "--app-name=Hermes", title, message],
            timeout=5,
            capture_output=True,
        )
    except FileNotFoundError:
        logger.debug("hermes-notification: notify-send not found")
    except Exception as e:
        logger.debug("hermes-notification: notify-send failed: %s", e)


def _linux_sound(sound_path: str) -> None:
    """Try pw-play → paplay → aplay in order."""
    if not sound_path:
        return
    for player in ("pw-play", "paplay", "aplay"):
        try:
            subprocess.Popen(
                [player, sound_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.debug("hermes-notification: %s failed: %s", player, e)
            return


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

def _windows_notify(title: str, message: str) -> None:
    # Uses BurntToast or falls back to a simple balloon via PowerShell
    ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.BalloonTipTitle = '{title.replace("'", "''")}'
$n.BalloonTipText  = '{message.replace("'", "''")}'
$n.Visible = $true
$n.ShowBalloonTip(5000)
Start-Sleep -Milliseconds 5500
$n.Visible = $false
$n.Dispose()
"""
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.debug("hermes-notification: powershell notify failed: %s", e)


def _windows_sound(sound_name: str) -> None:
    if not sound_name:
        return
    ps_script = f"[System.Media.SystemSounds]::{sound_name}.Play()"
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.debug("hermes-notification: powershell sound failed: %s", e)


# ---------------------------------------------------------------------------
# Unified notify
# ---------------------------------------------------------------------------

def _notify(title: str, message: str, sound: str) -> None:
    """Send notification + play sound in parallel, non-blocking."""
    sys = _current_platform()

    def _run():
        if sys == "macos":
            t = threading.Thread(target=_macos_sound, args=(sound,), daemon=True)
            t.start()
            _macos_notify(title, message)
            t.join(timeout=10)
        elif sys == "linux":
            t = threading.Thread(target=_linux_sound, args=(sound,), daemon=True)
            t.start()
            _linux_notify(title, message)
            t.join(timeout=10)
        elif sys == "windows":
            t = threading.Thread(target=_windows_sound, args=(sound,), daemon=True)
            t.start()
            _windows_notify(title, message)
            t.join(timeout=10)

    threading.Thread(target=_run, daemon=True, name="hermes-notification").start()


# ---------------------------------------------------------------------------
# Hook callback
# ---------------------------------------------------------------------------

def _on_post_llm_call(
    session_id: str = "",
    user_message: str = "",
    assistant_response: str = "",
    conversation_history: list = None,
    model: str = "",
    platform: str = "",
    **kwargs,
) -> None:
    """Called by Hermes after every completed AI response."""
    cfg = _load_config()

    if not cfg.get("enabled", True):
        return

    if len(assistant_response.strip()) < cfg.get("min_response_length", 10):
        return

    # Build preview body
    preview_len = cfg.get("preview_length", 100)
    if preview_len > 0 and assistant_response:
        body = assistant_response.strip()
        # Strip leading markdown code fences for cleaner preview
        if body.startswith("```"):
            nl = body.find("\n")
            body = body[nl + 1:] if nl != -1 else body
        body = body[:preview_len]
        if len(assistant_response.strip()) > preview_len:
            body += "…"
    else:
        body = "Response complete"

    _notify(
        title=cfg.get("title", "Hermes ✅"),
        message=body,
        sound=cfg.get("sound", "Glass"),
    )


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register the post_llm_call hook with Hermes."""
    global _config
    _config = _load_config()

    if not _config.get("enabled", True):
        logger.info("hermes-notification: disabled via config, skipping")
        return

    ctx.register_hook("post_llm_call", _on_post_llm_call)
    logger.info("hermes-notification: registered — will notify on every completed response")
