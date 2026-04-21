# hermes-notification 🔔

A plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that sends a **native macOS system notification** the moment Hermes finishes a response — with smart click-to-open behavior.

No more switching back to check if the AI is done. Just keep working, and let the notification bring you back when it's ready.

![macOS](https://img.shields.io/badge/macOS-supported-brightgreen?logo=apple)
![version](https://img.shields.io/badge/version-2.0.0-blue)
![python](https://img.shields.io/badge/python-3.8%2B-blue?logo=python)

---

<img width="366" height="78" alt="hermes notification preview" src="https://github.com/user-attachments/assets/0bbf72a5-eb05-42e2-a749-6649b0ad6ad7" />

---

## ✨ 功能特性

- 🔔 **每次 Hermes 回复后**自动弹出 macOS 原生通知（横幅 + 声音）
- 🖱️ **智能点击跳转**：
  - 如果 **hermes-web-ui 正在运行**（默认 `localhost:8648`）→ 点击通知直接在 **Chrome** 打开对应 session 页面
  - 如果是 **CLI 模式** → 点击通知自动**激活并聚焦终端窗口**（支持 iTerm2、Warp、Terminal 等）
- ⚡ **非阻塞**：通知在后台线程发送，完全不影响 Hermes 响应速度
- 🎵 通知声音可配置（默认 `Glass`，支持所有 macOS 系统声音）
- 📝 响应正文预览（可配置截取长度）
- 🔧 零侵入：纯插件，不修改 Hermes 核心代码
- ⚙️ 完全可配置：标题、声音、预览长度、最小响应长度等

---

## 🆕 v2.0 重点改动

### 1. 双模式智能点击跳转（核心新功能）

旧版只能发送通知，点击无任何动作。v2.0 完全重写了点击逻辑：

| 运行模式 | 点击行为 | 实现方式 |
|---------|---------|---------|
| Web UI 模式（`localhost:8648` 可访问） | 在 Chrome 打开 `http://localhost:8648/#/hermes/chat` | `terminal-notifier -open URL -activate com.google.chrome` |
| CLI 模式（终端直接运行） | 激活并聚焦当前终端窗口 | `terminal-notifier -execute <script>` + AppleScript |

### 2. 彻底抛弃 pyobjc

macOS 15 上 `NSUserNotificationCenter` 已被 Apple 废弃，`pyobjc` 调用直接返回 `None`，通知完全失效。v2.0 改为：

- **优先**：使用 [`terminal-notifier`](https://github.com/julienXX/terminal-notifier)（Homebrew 安装，功能完整）
- **降级兜底**：`osascript`（系统内置，无点击功能但通知正常显示）

### 3. 修复 `.sh` 脚本被 Script Editor 打开的 Bug

terminal-notifier 的 `-execute` 参数在 macOS 上会通过 Launch Services 打开文件。  
带 `.sh` 扩展名的文件会被 **Script Editor** 打开而非执行。

**修复方案**：激活终端的临时脚本写入 `/tmp/hermes_activate_terminal`（**无扩展名**），这样 macOS 会直接以可执行文件方式运行它。

### 4. 支持多种终端自动识别

CLI 模式下自动检测当前运行的终端 App，优先级顺序：

```
iTerm2 → iTerm → Warp → Terminal → Hyper → Alacritty → kitty
```

通过 AppleScript 查询 `System Events` 进程列表实现，无需额外配置。

---

## 📦 安装

### 1. 安装依赖（推荐）

```bash
brew install terminal-notifier
```

> 不安装也可以使用，会自动降级为 `osascript` 发送通知（但点击跳转功能不可用）。

### 2. 安装插件

```bash
git clone https://github.com/itgoyo/hermes-notification.git
mkdir -p ~/.hermes/plugins/hermes-notification
cp hermes-notification/__init__.py ~/.hermes/plugins/hermes-notification/
cp hermes-notification/plugin.yaml  ~/.hermes/plugins/hermes-notification/
```

一行版：

```bash
git clone https://github.com/itgoyo/hermes-notification.git && \
  mkdir -p ~/.hermes/plugins/hermes-notification && \
  cp hermes-notification/{__init__.py,plugin.yaml} ~/.hermes/plugins/hermes-notification/
```

### 3. 重启 Hermes

插件在启动时自动发现，日志中应出现：

```
hermes-notification: registered (v4 fixed)
```

---

## ⚙️ 配置

在 `~/.hermes/plugins/hermes-notification/config.json` 创建配置文件（可选，所有字段均有默认值）：

```json
{
    "enabled": true,
    "title": "Hermes ✅",
    "sound": "Glass",
    "preview_length": 80,
    "min_response_length": 10,
    "web_ui_port": 8648,
    "web_ui_host": "localhost"
}
```

| 字段 | 默认值 | 说明 |
|-----|--------|------|
| `enabled` | `true` | 是否启用插件 |
| `title` | `"Hermes ✅"` | 通知标题 |
| `sound` | `"Glass"` | 通知声音（macOS 系统声音名，留空则静音） |
| `preview_length` | `80` | 响应预览的最大字符数 |
| `min_response_length` | `10` | 少于此长度的响应不发送通知 |
| `web_ui_port` | `8648` | hermes-web-ui 端口 |
| `web_ui_host` | `"localhost"` | hermes-web-ui 主机 |

### 可用系统声音

```
Basso  Blow  Bottle  Frog  Funk  Glass  Hero  Morse  Ping  Pop  Purr
Sosumi  Submarine  Tink
```

---

## 🔍 工作原理

```
Hermes 完成回复
      ↓
post_llm_call hook 触发
      ↓
检测 localhost:8648 是否可访问
      ↓
┌─────────────────────┬──────────────────────────┐
│  Web UI 在运行       │  CLI 模式                 │
│  open_url = 页面URL  │  检测活跃终端 App          │
│  activate = Chrome  │  写 /tmp/hermes_activate_ │
│                     │  terminal（无扩展名脚本）   │
└─────────────────────┴──────────────────────────┘
      ↓
terminal-notifier 发送通知（后台线程）
      ↓（fallback）
osascript display notification
```

---

## 🛠️ 调试

开启 DEBUG 日志可以看到详细输出：

```bash
# 在 ~/.hermes/config.yaml 中设置
log_level: DEBUG
```

日志关键词：
- `hermes-notification: web-ui detected` — 检测到 Web UI 模式
- `hermes-notification: CLI mode, terminal=iTerm2` — CLI 模式，识别到终端
- `hermes-notification: terminal-notifier exit=0` — 通知发送成功

---

## 📋 系统要求

- macOS 10.14+
- Python 3.8+
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- `terminal-notifier`（可选，`brew install terminal-notifier`）

---

## 📄 License

MIT
