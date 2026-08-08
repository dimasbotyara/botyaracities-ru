#!/usr/bin/env python3
"""
    Интерактивный поиск русских городов
    Минималистичный CLI-инструмент
"""

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.document import Document
from prompt_toolkit.styles import Style

from cities_db import RUSSIAN_CITIES, normalize

# ─────────────────────────────────────────────
MAX_RESULTS = 40
ARROW = "\u25b6"   # ▶
DOT = "\u25cf"     # ●
DASH = "\u2500"    # ─


# ─────────────────────────────────────────────
#  Поиск
# ─────────────────────────────────────────────
def search_cities(query: str) -> list[str]:
    if not query.strip():
        return []

    q = normalize(query)
    starts = []
    contains = []

    for city in RUSSIAN_CITIES:
        c = normalize(city)
        if c.startswith(q):
            starts.append(city)
        elif q in c:
            contains.append(city)

    return (starts + contains)[:MAX_RESULTS]


# ─────────────────────────────────────────────
#  Состояние
# ─────────────────────────────────────────────
class State:
    def __init__(self):
        self.results: list[str] = []
        self.index: int = 0
        self.total: int = len(RUSSIAN_CITIES)

    def update(self, query: str):
        self.results = search_cities(query)
        self.index = 0

    def up(self):
        if self.results:
            self.index = max(0, self.index - 1)

    def down(self):
        if self.results:
            self.index = min(len(self.results) - 1, self.index + 1)


state = State()


# ─────────────────────────────────────────────
#  Подсветка совпадений
# ─────────────────────────────────────────────
def highlight(city: str, query: str, selected: bool) -> list[tuple[str, str]]:
    if not query:
        s = "class:sel" if selected else "class:city"
        return [(s, city)]

    q = normalize(query)
    idx = normalize(city).find(q)

    if idx == -1:
        s = "class:sel" if selected else "class:city"
        return [(s, city)]

    before = city[:idx]
    match = city[idx:idx + len(query)]
    after = city[idx + len(query):]

    if selected:
        parts = []
        if before:
            parts.append(("class:sel", before))
        parts.append(("class:sel-match", match))
        if after:
            parts.append(("class:sel", after))
        return parts
    else:
        parts = []
        if before:
            parts.append(("class:city", before))
        parts.append(("class:match", match))
        if after:
            parts.append(("class:city", after))
        return parts


# ─────────────────────────────────────────────
#  Отрисовка
# ─────────────────────────────────────────────
def get_header():
    return [("class:title", f"  {DASH * 3} Поиск городов России {DASH * 3}\n")]


def get_results():
    q = buf.text.strip()

    if not q:
        return [
            ("class:dim", "\n  Начните вводить название города\n\n"),
            ("class:dim", f"  {DOT} "),
            ("class:key", "Up/Down"),
            ("class:dim", "  навигация\n"),
            ("class:dim", f"  {DOT} "),
            ("class:key", "Enter"),
            ("class:dim", "    подставить в поле\n"),
            ("class:dim", f"  {DOT} "),
            ("class:key", "Esc"),
            ("class:dim", "      выход\n\n"),
            ("class:dim", f"  Всего в базе: "),
            ("class:accent", f"{state.total}"),
            ("class:dim", " городов\n"),
        ]

    if not state.results:
        return [
            ("class:warn", f'\n  Ничего не найдено по запросу "'),
            ("class:accent", q),
            ("class:warn", '"\n'),
        ]

    lines: list[tuple[str, str]] = []

    count = len(state.results)
    lines.append(("class:dim", f"\n  Найдено: "))
    lines.append(("class:accent", f"{count}"))
    if count >= MAX_RESULTS:
        lines.append(("class:dim", f"  (показаны первые {MAX_RESULTS})"))
    lines.append(("class:dim", "\n"))
    lines.append(("class:sep", f"  {DASH * 32}\n"))

    for i, city in enumerate(state.results):
        selected = i == state.index
        if selected:
            lines.append(("class:arrow", f"  {ARROW} "))
        else:
            lines.append(("", "    "))
        lines.extend(highlight(city, q, selected))
        lines.append(("", "\n"))

    return lines


def get_status():
    return [
        ("class:key", " Esc "),
        ("class:dim", " выход  "),
        ("class:key", " Tab "),
        ("class:dim", " подставить  "),
        ("class:key", " Ctrl+L "),
        ("class:dim", " очистить"),
    ]


# ─────────────────────────────────────────────
#  Буфер и клавиши
# ─────────────────────────────────────────────
def on_change(b: Buffer):
    state.update(b.text)
    app.invalidate()


buf = Buffer(on_text_changed=on_change, multiline=False)

kb = KeyBindings()


@kb.add("escape")
def _(e):
    e.app.exit()


@kb.add("c-c")
def _(e):
    e.app.exit()


@kb.add("up")
def _(e):
    state.up()


@kb.add("down")
def _(e):
    state.down()


@kb.add("enter")
def _(e):
    if state.results:
        city = state.results[state.index]
        buf.set_document(Document(city, len(city)), bypass_readonly=True)
        state.update(city)


@kb.add("tab")
def _(e):
    if state.results:
        city = state.results[state.index]
        buf.set_document(Document(city, len(city)), bypass_readonly=True)
        state.update(city)


@kb.add("c-l")
def _(e):
    buf.set_document(Document(""), bypass_readonly=True)
    state.update("")


# ─────────────────────────────────────────────
#  Компоновка
# ─────────────────────────────────────────────

input_window = Window(
    content=BufferControl(buffer=buf, focusable=True),
    height=1,
)

input_row = VSplit([
    Window(
        FormattedTextControl([("class:prompt", f"  {ARROW} Город: ")]),
        width=14,
        height=1,
        dont_extend_width=True,
    ),
    input_window,
])

root = HSplit([
    Window(FormattedTextControl(get_header), height=2),
    input_row,
    Window(height=1, char=DASH, style="class:sep"),
    Window(
        FormattedTextControl(get_results),
        right_margins=[ScrollbarMargin(display_arrows=False)],
        wrap_lines=True,
    ),
    Window(height=1, char=DASH, style="class:sep"),
    Window(FormattedTextControl(get_status), height=1),
])

layout = Layout(root, focused_element=input_window)


# ─────────────────────────────────────────────
#  Стиль
# ─────────────────────────────────────────────
style = Style.from_dict({
    "title":     "#e94560 bold",
    "prompt":    "#e94560 bold",
    "sep":       "#444444",

    "city":      "#cccccc",
    "match":     "#e94560 bold underline",
    "arrow":     "#e94560 bold",
    "sel":       "#ffffff bold",
    "sel-match": "#ffdd57 bold underline",

    "dim":       "#777777",
    "accent":    "#e94560 bold",
    "key":       "#e94560 bold",
    "warn":      "#ff6b6b italic",
})


# ─────────────────────────────────────────────
#  Запуск
# ─────────────────────────────────────────────
app = Application(
    layout=layout,
    key_bindings=kb,
    style=style,
    full_screen=True,
    mouse_support=True,
)


def main():
    app.run()
    print(f"\n  До встречи! \U0001f3d8\n")


if __name__ == "__main__":
    main()