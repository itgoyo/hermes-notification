# hermes-notification 🔔

A plugin for [Hermes Agent](https://github.com/NousResearch/hermes) that sends a **native system notification** (banner + sound) the moment Hermes finishes a response.

No more constantly switching back to check if the AI is done — just keep working and let the notification tell you when it's ready.

![macOS notification preview](https://img.shields.io/badge/macOS-supported-brightgreen?logo=apple) ![Linux notification preview](https://img.shields.io/badge/Linux-supported-brightgreen?logo=linux) ![Windows notification preview](https://img.shields.io/badge/Windows-supported-brightgreen?logo=windows)

---

<img width="366" height="78" alt="image" src="https://github.com/user-attachments/assets/0bbf72a5-eb05-42e2-a749-6649b0ad6ad7" />


## ✨ Features

- **macOS** — native banner via `osascript` + sound via `afplay`
- **Linux** — native banner via `notify-send` + sound via `pw-play` / `paplay` / `aplay`
- **Windows** — system tray balloon via PowerShell + `SystemSounds`
- Response preview in the notification body (first N characters)
- Fully configurable: title, sound, preview length, min response length
- Non-blocking: runs in a background thread, never slows down Hermes
- Zero external dependencies — uses only tools that ship with your OS

---

## 📦 Installation

### 1. Copy the plugin into Hermes

```bash
# Clone this repo
git clone https://github.com/itgoyo/hermes-notification.git

# Copy plugin files into Hermes plugin directory
mkdir -p ~/.hermes/plugins/hermes-notification
cp hermes-notification/__init__.py ~/.hermes/plugins/hermes-notification/
cp hermes-notification/plugin.yaml  ~/.hermes/plugins/hermes-notification/
```

Or with a one-liner:

```bash
git clone https://github.com/itgoyo/hermes-notification.git && \
mkdir -p ~/.hermes/plugins/hermes-notification && \
cp hermes-notification/{__init__.py,plugin.yaml} ~/.hermes/plugins/hermes-notification/
```

### 2. Restart Hermes

The plugin is auto-discovered on startup. You should see in the logs:

```
hermes-notification: registered — will notify on every completed response
```

### 3. (macOS) Allow notifications

On first run, macOS may ask for permission. If the banner doesn't appear:

> **System Settings → Notifications → Script Editor** (or your terminal app) → Allow notifications

---

## ⚙️ Configuration

Create `~/.hermes/plugins/hermes-notification/config.json` to override any defaults:

```json
{
    "sound": "Glass",
    "title": "Hermes ✅",
    "preview_length": 100,
    "min_response_length": 10,
    "enabled": true
}
```

| Key | Default | Description |
|---|---|---|
| `sound` | `"Glass"` | **macOS**: any name from `/System/Library/Sounds/` (without `.aiff`), or a full file path, or `""` to disable sound. **Linux**: full path to a `.wav`/`.oga` file, or `""`. **Windows**: `"SystemAsterisk"`, `"SystemExclamation"`, `"SystemHand"`, `"SystemQuestion"`, or `""`. |
| `title` | `"Hermes ✅"` | Title shown in the notification banner |
| `preview_length` | `100` | Characters of the response to show in the body (`0` = no preview) |
| `min_response_length` | `10` | Responses shorter than this are silently skipped |
| `enabled` | `true` | Set to `false` to disable the plugin without uninstalling |

### macOS sound options

All built-in macOS sounds work out of the box:

`Basso` `Blow` `Bottle` `Frog` `Funk` `Glass` `Hero` `Morse` `Ping` `Pop` `Purr` `Sosumi` `Submarine` `Tink`

---

## 🧪 Testing

Test the notification immediately without starting a full conversation:

```bash
python3 - <<'EOF'
import sys
sys.path.insert(0, "~/.hermes/plugins/hermes-notification")
from hermes_notification import _notify
_notify("Hermes ✅", "This is a test notification!", "Glass")
import time; time.sleep(2)
EOF
```

Or trigger it directly from the plugin file:

```bash
cd ~/.hermes/plugins/hermes-notification
python3 -c "
from __init__ import _notify
_notify('Hermes ✅', 'Test — plugin is working!', 'Glass')
import time; time.sleep(2)
"
```

---

## 🔧 How It Works

Hermes exposes a `post_llm_call` hook that fires after every completed AI response. This plugin registers a callback on that hook:

```
You send message → Hermes processes → AI responds
                                            ↓
                              post_llm_call hook fires
                                            ↓
                       ┌────────────────────────────────┐
                       │  hermes-notification plugin     │
                       │  ┌─────────────┐  ┌─────────┐  │
                       │  │ osascript   │  │ afplay  │  │  ← macOS
                       │  │ notify-send │  │ pw-play │  │  ← Linux
                       │  │ PowerShell  │  │ PS Media│  │  ← Windows
                       │  └─────────────┘  └─────────┘  │
                       └────────────────────────────────┘
                                            ↓
                              Banner appears on screen 🔔
```

The callback runs in a **background daemon thread** so it never blocks or delays Hermes responses.

---

## 🗂️ File Structure

```
hermes-notification/
├── __init__.py          # Plugin logic (hooks, platform detection, notify/sound)
├── plugin.yaml          # Plugin manifest (name, version, hooks)
├── config.example.json  # Example configuration file
└── README.md
```

After installation:
```
~/.hermes/plugins/hermes-notification/
├── __init__.py
├── plugin.yaml
└── config.json          # Your personal config (optional, not tracked by git)
```

---

## 🤝 Contributing

Pull requests are welcome! If you add support for a new platform or notification backend, please include:
1. Platform detection logic in `_current_platform()`
2. A `_<platform>_notify()` and `_<platform>_sound()` function
3. A branch in `_notify()` calling your new functions
4. An update to this README

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
