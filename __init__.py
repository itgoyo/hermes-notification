"""
hermes-notification plugin  (v4 — terminal-notifier fixed)
==========================================================
每次 Hermes 回复后发送 macOS 系统通知，点击可跳转。

点击行为：
- web-ui 在运行 (localhost:8648) → 点击在 Chrome/默认浏览器打开页面
- CLI 模式 → 点击激活终端窗口

关键修复：
1. Web UI 模式用 -open URL + -activate bundleID，不用 -execute
2. 终端模式的脚本文件不带 .sh 扩展名（.sh 在 macOS 会被 Script Editor 打开！）
3. 不再依赖 pyobjc（macOS 15 上 NSUserNotificationCenter 已废弃返回 None）

Config (optional) ~/.hermes/plugins/hermes-notification/config.json:
{
    "sound": "Glass",
    "title": "Hermes ✅",
    "preview_length": 80,
    "min_response_length": 10,
    "enabled": true,
    "web_ui_port": 8648,
    "web_ui_host": "localhost"
}
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

DEFAULTS = {
    "sound": "Glass",
    "title": "Hermes ✅",
    "preview_length": 80,
    "min_response_length": 10,
    "enabled": True,
    "web_ui_port": 8648,
    "web_ui_host": "localhost",
}

# 注意：不能用 .sh 扩展名！macOS 会用 Script Editor 打开 .sh 文件！
_ACTIVATE_SCRIPT = "/tmp/hermes_activate_terminal"


def _load_config() -> dict:
    config_path = (
        Path.home() / ".hermes" / "plugins" / "hermes-notification" / "config.json"
    )
    cfg = dict(DEFAULTS)
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg.update(json.load(f))
        except Exception as e:
            logger.warning("hermes-notification: failed to load config: %s", e)
    return cfg


# ---------------------------------------------------------------------------
# Web UI detection
# ---------------------------------------------------------------------------

def _is_web_ui_running(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _build_web_ui_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/#/hermes/chat"


# ---------------------------------------------------------------------------
# Terminal app detection
# ---------------------------------------------------------------------------

_TERMINAL_APPS = ["iTerm2", "iTerm", "Warp", "Terminal", "Hyper", "Alacritty", "kitty"]


def _get_terminal_app() -> str | None:
    apps_as = "{" + ", ".join(f'"{a}"' for a in _TERMINAL_APPS) + "}"
    script = f"""
tell application "System Events"
    set termApps to {apps_as}
    repeat with appName in termApps
        if exists (process appName) then
            return appName
        end if
    end repeat
    return ""
end tell
"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=3,
        )
        app = result.stdout.strip()
        return app if app else None
    except Exception:
        return None


def _write_activate_script(term_app: str) -> str:
    """
    写激活终端的可执行文件到 /tmp/hermes_activate_terminal（无扩展名！）
    有扩展名 .sh 的文件在 macOS 上会被 Script Editor 打开。
    """
    content = "#!/bin/bash\n" f'osascript -e \'tell application "{term_app}" to activate\'\n'
    with open(_ACTIVATE_SCRIPT, "w") as f:
        f.write(content)
    os.chmod(_ACTIVATE_SCRIPT, 0o755)
    return _ACTIVATE_SCRIPT


# ---------------------------------------------------------------------------
# terminal-notifier path
# ---------------------------------------------------------------------------

def _tn_path() -> str | None:
    path = shutil.which("terminal-notifier")
    if path:
        return path
    for p in [
        "/opt/homebrew/bin/terminal-notifier",
        "/usr/local/bin/terminal-notifier",
    ]:
        if os.path.exists(p):
            return p
    return None


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def _send_notification(
    title: str,
    message: str,
    sound: str,
    open_url: str | None,
    terminal_app: str | None,
) -> None:
    tn = _tn_path()

    if tn:
        cmd = [
            tn,
            "-title",   title,
            "-message", message,
            "-group",   "hermes",
        ]
        if sound:
            cmd += ["-sound", sound]

        if open_url:
            # Web UI 模式：-open 传 URL，-activate 激活 Chrome
            # 不用 -execute，避免任何脚本打开问题
            cmd += ["-open", open_url]
            cmd += ["-activate", "com.google.chrome"]
        elif terminal_app:
            # 终端模式：-execute 传无扩展名的可执行文件
            # 关键：不能是 .sh 文件，否则 macOS 用 Script Editor 打开！
            script_path = _write_activate_script(terminal_app)
            cmd += ["-execute", script_path]

        try:
            result = subprocess.run(cmd, timeout=5, capture_output=True)
            logger.debug(
                "hermes-notification: terminal-notifier exit=%d stderr=%s",
                result.returncode, result.stderr.decode(errors="replace"),
            )
            return
        except Exception as e:
            logger.debug("hermes-notification: terminal-notifier failed: %s", e)

    # Fallback：osascript（无点击功能）
    _send_osascript_notification(title, message, sound)


def _send_osascript_notification(title: str, message: str, sound: str) -> None:
    safe_title   = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_message}" with title "{safe_title}"'
    if sound:
        sound_path = f"/System/Library/Sounds/{sound}.aiff"
        if os.path.exists(sound_path):
            subprocess.Popen(
                ["afplay", sound_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception as e:
        logger.debug("hermes-notification: osascript failed: %s", e)


def _notify_async(
    title: str,
    message: str,
    sound: str,
    open_url: str | None,
    terminal_app: str | None,
) -> None:
    threading.Thread(
        target=_send_notification,
        args=(title, message, sound, open_url, terminal_app),
        daemon=True,
        name="hermes-notification",
    ).start()


# ---------------------------------------------------------------------------
# Hook
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
    cfg = _load_config()

    if not cfg.get("enabled", True):
        return

    min_len = cfg.get("min_response_length", 10)
    if len(assistant_response.strip()) < min_len:
        return

    # 构建通知正文
    preview_len = cfg.get("preview_length", 80)
    body = assistant_response.strip()
    if body.startswith("```"):
        nl = body.find("\n")
        body = body[nl + 1:] if nl != -1 else body
    body = body[:preview_len]
    if len(assistant_response.strip()) > preview_len:
        body += "…"

    title    = cfg.get("title", "Hermes ✅")
    sound    = cfg.get("sound", "Glass")
    web_host = cfg.get("web_ui_host", "localhost")
    web_port = cfg.get("web_ui_port", 8648)

    open_url: str | None = None
    terminal_app: str | None = None

    if _is_web_ui_running(web_host, web_port):
        open_url = _build_web_ui_url(web_host, web_port)
        logger.debug("hermes-notification: web-ui detected → %s", open_url)
    else:
        terminal_app = _get_terminal_app()
        logger.debug("hermes-notification: CLI mode, terminal=%s", terminal_app)

    _notify_async(title, body, sound, open_url, terminal_app)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    cfg = _load_config()
    if not cfg.get("enabled", True):
        logger.info("hermes-notification: disabled, skipping")
        return

    ctx.register_hook("post_llm_call", _on_post_llm_call)
    logger.info("hermes-notification: registered (v4 fixed)")
