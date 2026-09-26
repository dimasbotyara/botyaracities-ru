# 🏙️ botyaracities-ru

🇬🇧 **English** · [🇷🇺 Русский](README.ru.md)

> **A LAN multiplayer "Cities of Russia" word game — play the classic word-chain with a friend over your local network.**

Two players take turns naming Russian cities. Each city must start with the last letter of the previous one. Miss the 30-second timer or repeat a city and you lose a life. Three lives, and you're out. Pure Pygame client + asyncio TCP server + a bonus CLI city-search tool.

**⚠️ Linux / macOS / Windows. Uses raw TCP sockets — designed for LAN, not the public internet.**

---

## ✨ Features

### 🎮 Core Gameplay
- **Classic word-chain rules** — name a city starting with the last letter of the previous one
- **Auto-validated** against a bundled database of **~400 real Russian cities** (from Абакан to Яхрома)
- **Forbidden letters** (`ь`, `ъ`, `ы`, `й`, `ё`) auto-skipped — the game picks the previous real letter
- **No repeats** — once a city is named, it's off the board
- **Score** = number of letters in the city you name (Ялта = +4, Москва = +6, Санкт-Петербург = +15)

### 💖 Lives & Timer
- **3 lives per player** — lose one on a timeout, keep playing
- **30 seconds per turn** for the first 10 turns, **15 seconds** after — the game gets spicy fast
- **Animated pulsing timer bar** — green → yellow → red as time runs out
- **First to lose all 3 lives loses** — clean, dramatic, done

### 🎨 Juice & Visuals
- **Animated aurora background** with drifting nebula circles
- **150 twinkling stars** scrolling across the screen
- **Particle system** — bursts on city accept, red explosion on reject, confetti on win
- **Floating text** animations for scores, warnings, and life losses
- **Screen shake** on errors, timeouts, and critical hits
- **Glassmorphic panels** with inner highlights and glow effects
- **Animated title** with per-character wave motion
- **Big animated "next letter" indicator** that pulses and scales in
- **Real-time opponent typing indicator** — see what they're typing as they type it

### 🧠 Smart Server Logic
- **Auto-relaxation**: if no city exists starting with the required letter, the server picks a random available letter and warns both players
- **Random first player** each match
- **Fair validation** — rejects invalid cities, repeats, and wrong first letters with specific reason messages
- **Graceful end-game** — proper cleanup, no dangling sockets, clean shutdown on disconnect
- **Handles 2 players** — first come, first served, room closes when both join

### 🖥️ Bonus: CLI City Search Tool
A separate `search.py` gives you an **interactive fuzzy-search CLI** for the entire city database:
- Type to search, matches highlight in red
- Arrow keys to navigate, Enter to insert into buffer
- Built with `prompt_toolkit` — mouse support, scrollbar, custom theme
- Perfect for cheating… er, "practicing"

### 🌐 Network Protocol
- **Simple JSON + 4-byte length prefix** over raw TCP (`protocol.py`)
- **Async server** (`asyncio`) with per-player listener threads
- **Synchronous client** using a dedicated receive thread
- **Typing events streamed in real time**
- Protocol messages: `join`, `wait`, `game_start`, `turn_start`, `timer_tick`, `typing`, `submit`, `city_accepted`, `city_rejected`, `timeout`, `game_over`, `disconnect`

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (uses `str | None` unions)
- **pygame** (client)
- **prompt_toolkit** (CLI search tool, optional)

### Install

```bash
git clone https://github.com/dimasbotyara/botyaracities-ru.git
cd botyaracities-ru

python -m venv .venv
source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate      # Windows

pip install pygame prompt_toolkit
```

### Run a Match

**Terminal 1 — start the server:**
```bash
python server.py
# or with a custom port:
python server.py 5555
```

**Terminal 2 & 3 — start two clients:**
```bash
python client.py
```

In each client:
1. Enter your name
2. Enter the server IP (`localhost` if same machine, otherwise the LAN IP)
3. Set the port (default `5555`)
4. Hit **ПОДКЛЮЧИТЬСЯ**

The match starts automatically once both players are in.

### Bonus: CLI Search

```bash
python search.py
```

Type to search cities. Use `↑`/`↓` to navigate, `Enter` to insert, `Esc` to quit.

---

## 🎮 Controls

| Screen | Key / Action |
|--------|--------------|
| **Menu** | Click to focus inputs, type your name / IP / port |
| **Menu** | Click **ПОДКЛЮЧИТЬСЯ** or press it with mouse |
| **Playing** | Type the city in the bottom input box |
| **Playing** | `Enter` to submit, or click **ОТПРАВИТЬ** |
| **Any** | `Alt+F4` / close window to quit |

---

## 📂 Project Structure

```
botyaracities-ru/
├── server.py          # 🎯 Game server — accepts 2 players, runs turn loop, validates cities
├── client.py          # 🖼️ Pygame client — UI, particles, animations, network thread
├── protocol.py        # 🔌 JSON-over-TCP: 4-byte length prefix + UTF-8 payload
├── cities_db.py       # 📚 ~400 Russian cities + letter rules + normalization
├── search.py          # 🔍 Bonus CLI fuzzy-search tool (prompt_toolkit)
└── LICENSE
```

Five files. No dependencies except `pygame` (client) and `prompt_toolkit` (CLI tool).

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Client UI** | Pygame |
| **Server** | Python `socket` + `threading` |
| **Client networking** | Background thread + lock-protected message queue |
| **Protocol** | JSON + struct-packed length prefix over TCP |
| **City database** | Bundled Python list + normalized set + per-letter index |
| **CLI tool** | prompt_toolkit |
| **Persistence** | None — matches are ephemeral |

---

## 🧠 How the City Validation Works

Every city goes through three checks on the server:

1. **Is it in the database?** — normalized lookup in `CITIES_SET`
2. **Has it been used?** — checked against `used_cities`
3. **Does it start with the required letter?** — first char compared to `required_letter`

If it passes → city is added to `used_cities`, its last valid letter becomes the next required letter, and the player scores `len(city)` points.

If the *next* required letter has **zero available cities** left, the server picks a random available letter and warns both players with a floating message. Smart, friendly, and prevents the game from deadlocking.

---

## 🔧 Customization

### Adding more cities
Edit `cities_db.py` — just append to `RUSSIAN_CITIES`. The `CITIES_SET` and `CITIES_BY_LETTER` indexes are rebuilt automatically at import time.

### Changing turn time
Edit `GameServer.get_turn_time()` in `server.py`:
```python
def get_turn_time(self):
    if self.turn_number < 10:
        return 30
    return 15
```

### Changing starting lives
In `server.py`, modify `self.lives = [3, 3]`.

### Changing colors / theme
All palette constants live at the top of `client.py` (`BG_DARK`, `ACCENT`, `GOLD`, etc.). Tweak, reload, done.

### Adding more players
Currently hard-coded for 2. Look at `listen(2)` in `server.py` and the client's `player_id` handling — the architecture supports N players with minor changes.

---

## 🐛 Troubleshooting

**Can't connect between two machines**
- Make sure the server is listening on `0.0.0.0` (default)
- Check your firewall — port `5555` must be open on the server machine
- Use the server's **LAN IP** (e.g. `192.168.1.42`), not `localhost`

**"Это не город из базы!" on a real city**
- The database has ~400 cities. Uncommon ones might be missing — add them to `cities_db.py` and restart the server.

**Pygame window is black on launch**
- Ensure `pygame` is installed in the same venv you launched the client with.
- On HiDPI displays, you may need `SDL_VIDEO_X11_SCALING=1 python client.py`.

**Search tool crashes on import**
- `pip install prompt_toolkit` — the search tool is a separate optional dependency.

**Timer keeps ticking during lag**
- The server sends `timer_tick` messages every 300ms; the client trusts these, so a laggy connection will show frozen time. Server-side timeout still fires correctly.

---

## 🚧 Roadmap

- ⬜ Support for 3+ players
- ⬜ Global leaderboard (persisted across matches)
- ⬜ More languages (world cities, not just Russia)
- ⬜ Sound effects for accept / reject / timeout
- ⬜ Reconnect support if a player drops

---

## ⚠️ Disclaimer

This is a hobby project. It uses **unencrypted TCP sockets** and is intended **for trusted LANs only**. Do not expose `server.py` to the public internet without adding TLS and rate limiting.

---

## 📜 License

MIT — see [LICENSE](LICENSE).

---

## 👤 Author

**dimasbotyara** — [@dimasbotyara](https://github.com/dimasbotyara)

Made with 🏙️, ☕, and a surprising amount of aurora shaders in pure Pygame.

---

<div align="center">

**If you out-clicked your friend with a 12-letter city, drop a ⭐**

</div>
