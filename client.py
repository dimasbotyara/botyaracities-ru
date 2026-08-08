"""
Клиент игры "Города России" — Pygame.
Запуск: python client.py
"""
import pygame
import socket
import threading
import sys
import math
import random
import time
from protocol import send_message_sync, recv_message_sync
from cities_db import RUSSIAN_CITIES

# ============================================================
# КОНСТАНТЫ
# ============================================================
SCREEN_W, SCREEN_H = 1200, 800
FPS = 60

# Цветовая палитра
BG_DARK = (15, 15, 35)
BG_GRADIENT_TOP = (20, 20, 50)
BG_GRADIENT_BOT = (10, 10, 30)
ACCENT = (0, 200, 255)
ACCENT2 = (255, 100, 150)
GOLD = (255, 215, 0)
WHITE = (255, 255, 255)
GRAY = (150, 150, 170)
DARK_GRAY = (60, 60, 80)
RED = (255, 60, 60)
GREEN = (60, 255, 120)
PANEL_BG = (25, 25, 55, 200)
INPUT_BG = (35, 35, 65)
INPUT_ACTIVE = (45, 45, 85)
SHADOW = (0, 0, 0, 100)

pygame.init()
pygame.mixer.init()


# ============================================================
# PARTICLE SYSTEM
# ============================================================
class Particle:
    def __init__(self, x, y, color=None, size=None, lifetime=None, velocity=None, gravity=0):
        self.x = x
        self.y = y
        self.color = color or random.choice([ACCENT, ACCENT2, GOLD, GREEN, WHITE])
        self.size = size or random.uniform(2, 6)
        self.original_size = self.size
        self.lifetime = lifetime or random.uniform(0.5, 2.0)
        self.max_lifetime = self.lifetime
        if velocity:
            self.vx, self.vy = velocity
        else:
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 200)
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed
        self.gravity = gravity
        self.alpha = 255

        self.current_player = -1
        self.required_letter = None
        self.scores = [0, 0]
        self.lives = [3, 3]  # 🆕 ЖИЗНИ!
        self.turn_time = 30
        self.time_remaining = 30

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.lifetime -= dt
        progress = max(0, self.lifetime / self.max_lifetime)
        self.alpha = int(255 * progress)
        self.size = self.original_size * progress
        return self.lifetime > 0

    def draw(self, surface):
        if self.alpha <= 0 or self.size <= 0:
            return
        s = max(1, int(self.size))
        color = (*self.color[:3], min(255, self.alpha))
        temp = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        pygame.draw.circle(temp, color, (s, s), s)
        surface.blit(temp, (int(self.x) - s, int(self.y) - s))


class ParticleSystem:
    def __init__(self):
        self.particles: list[Particle] = []

    def emit(self, x, y, count=20, **kwargs):
        for _ in range(count):
            self.particles.append(Particle(x, y, **kwargs))

    def emit_burst(self, x, y, count=50, colors=None):
        """Красивый взрыв частиц."""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(100, 400)
            color = random.choice(colors or [ACCENT, ACCENT2, GOLD, GREEN])
            self.particles.append(Particle(
                x, y,
                color=color,
                size=random.uniform(3, 8),
                lifetime=random.uniform(0.8, 2.5),
                velocity=(math.cos(angle) * speed, math.sin(angle) * speed),
                gravity=150
            ))

    def emit_confetti(self, count=100):
        """Конфетти по всему экрану."""
        colors = [ACCENT, ACCENT2, GOLD, GREEN, RED, WHITE, (255, 165, 0)]
        for _ in range(count):
            x = random.uniform(0, SCREEN_W)
            self.particles.append(Particle(
                x, -10,
                color=random.choice(colors),
                size=random.uniform(4, 10),
                lifetime=random.uniform(3, 6),
                velocity=(random.uniform(-50, 50), random.uniform(100, 300)),
                gravity=50
            ))

    def emit_trail(self, x, y, color=ACCENT):
        """Маленький след."""
        self.particles.append(Particle(
            x + random.uniform(-5, 5),
            y + random.uniform(-5, 5),
            color=color,
            size=random.uniform(1, 3),
            lifetime=random.uniform(0.3, 0.8),
            velocity=(random.uniform(-20, 20), random.uniform(-40, -10)),
            gravity=0
        ))

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)


# ============================================================
# FLOATING TEXT ANIMATION
# ============================================================
class FloatingText:
    def __init__(self, text, x, y, color=WHITE, font_size=28, lifetime=2.0):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.font = pygame.font.Font(None, font_size)
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.alpha = 255
        self.vy = -60

    def update(self, dt):
        self.y += self.vy * dt
        self.lifetime -= dt
        progress = max(0, self.lifetime / self.max_lifetime)
        self.alpha = int(255 * progress)
        return self.lifetime > 0

    def draw(self, surface):
        if self.alpha <= 0:
            return
        rendered = self.font.render(self.text, True, self.color)
        rendered.set_alpha(self.alpha)
        rect = rendered.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(rendered, rect)


# ============================================================
# BACKGROUND STARS
# ============================================================
class Star:
    def __init__(self):
        self.x = random.uniform(0, SCREEN_W)
        self.y = random.uniform(0, SCREEN_H)
        self.size = random.uniform(1, 3)
        self.speed = random.uniform(0.3, 1.5)
        self.phase = random.uniform(0, 2 * math.pi)

    def update(self, dt, t):
        self.y += self.speed * dt * 20
        if self.y > SCREEN_H:
            self.y = 0
            self.x = random.uniform(0, SCREEN_W)
        self.brightness = int(128 + 127 * math.sin(t * self.speed + self.phase))

    def draw(self, surface):
        color = (self.brightness, self.brightness, min(255, self.brightness + 50))
        s = max(1, int(self.size))
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), s)


# ============================================================
# BUTTON
# ============================================================
class Button:
    def __init__(self, x, y, w, h, text, color=ACCENT, font_size=30):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.font = pygame.font.Font(None, font_size)
        self.hover = False
        self.click_anim = 0
        self.glow = 0

    def update(self, mouse_pos, dt):
        self.hover = self.rect.collidepoint(mouse_pos)
        if self.click_anim > 0:
            self.click_anim -= dt * 5
        if self.hover:
            self.glow = min(1, self.glow + dt * 4)
        else:
            self.glow = max(0, self.glow - dt * 4)

    def draw(self, surface):
        # Glow effect
        if self.glow > 0:
            glow_surf = pygame.Surface((self.rect.w + 20, self.rect.h + 20), pygame.SRCALPHA)
            glow_alpha = int(60 * self.glow)
            pygame.draw.rect(glow_surf, (*self.color, glow_alpha),
                           (0, 0, self.rect.w + 20, self.rect.h + 20),
                           border_radius=15)
            surface.blit(glow_surf, (self.rect.x - 10, self.rect.y - 10))

        # Shadow
        shadow_rect = self.rect.move(3, 3)
        pygame.draw.rect(surface, (0, 0, 0, 80), shadow_rect, border_radius=12)

        # Button body
        scale = 1 - self.click_anim * 0.05
        draw_rect = self.rect.copy()
        if scale != 1:
            draw_rect.inflate_ip(-int(self.rect.w * (1 - scale)),
                                -int(self.rect.h * (1 - scale)))

        # Gradient-like button
        color = tuple(min(255, c + int(30 * self.glow)) for c in self.color[:3])
        pygame.draw.rect(surface, color, draw_rect, border_radius=12)
        # Highlight
        highlight = pygame.Surface((draw_rect.w, draw_rect.h // 2), pygame.SRCALPHA)
        highlight.fill((255, 255, 255, 30))
        surface.blit(highlight, draw_rect.topleft)
        # Border
        pygame.draw.rect(surface, tuple(min(255, c + 50) for c in color),
                        draw_rect, 2, border_radius=12)

        # Text
        text_surf = self.font.render(self.text, True, WHITE)
        text_rect = text_surf.get_rect(center=draw_rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.click_anim = 1
                return True
        return False


# ============================================================
# INPUT BOX
# ============================================================
class InputBox:
    def __init__(self, x, y, w, h, placeholder=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = ""
        self.placeholder = placeholder
        self.font = pygame.font.Font(None, 36)
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0
        self.shake_amount = 0
        self.glow_color = ACCENT

    def handle_event(self, event) -> str | None:
        """Возвращает текст при нажатии Enter."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                result = self.text
                self.text = ""
                return result
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                if event.unicode and event.unicode.isprintable():
                    self.text += event.unicode
        return None

    def shake(self):
        self.shake_amount = 10

    def update(self, dt):
        self.cursor_timer += dt
        if self.cursor_timer > 0.5:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible
        if self.shake_amount > 0:
            self.shake_amount *= 0.9
            if self.shake_amount < 0.5:
                self.shake_amount = 0

    def draw(self, surface):
        offset_x = int(math.sin(time.time() * 30) * self.shake_amount)

        draw_rect = self.rect.move(offset_x, 0)

        # Glow
        if self.active:
            glow = pygame.Surface((draw_rect.w + 16, draw_rect.h + 16), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*self.glow_color, 40),
                           (0, 0, draw_rect.w + 16, draw_rect.h + 16),
                           border_radius=14)
            surface.blit(glow, (draw_rect.x - 8, draw_rect.y - 8))

        # Background
        color = INPUT_ACTIVE if self.active else INPUT_BG
        pygame.draw.rect(surface, color, draw_rect, border_radius=10)
        border_color = self.glow_color if self.active else DARK_GRAY
        pygame.draw.rect(surface, border_color, draw_rect, 2, border_radius=10)

        # Text
        if self.text:
            text_surf = self.font.render(self.text, True, WHITE)
        else:
            text_surf = self.font.render(self.placeholder, True, GRAY)

        # Clip text to input box
        clip_rect = pygame.Rect(draw_rect.x + 12, draw_rect.y, draw_rect.w - 24, draw_rect.h)
        text_rect = text_surf.get_rect(midleft=(draw_rect.x + 15, draw_rect.centery))

        # Scroll text if too long
        if text_rect.right > draw_rect.right - 15:
            text_rect.right = draw_rect.right - 15

        old_clip = surface.get_clip()
        surface.set_clip(clip_rect)
        surface.blit(text_surf, text_rect)
        surface.set_clip(old_clip)

        # Cursor
        if self.active and self.cursor_visible:
            cursor_x = min(text_rect.right + 2, draw_rect.right - 15)
            pygame.draw.line(surface, WHITE,
                           (cursor_x, draw_rect.y + 8),
                           (cursor_x, draw_rect.bottom - 8), 2)


# ============================================================
# GAME CLIENT
# ============================================================
class GameClient:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("🏙️ Города России — Онлайн")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.Font(None, 72)
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 28)
        self.font_tiny = pygame.font.Font(None, 22)

        # State
        self.state = 'menu'  # menu, connecting, waiting, playing, game_over
        self.sock: socket.socket | None = None
        self.player_id = -1
        self.player_names = []
        self.my_name = ""

        # Game state
        self.current_player = -1
        self.required_letter = None
        self.scores = [0, 0]
        self.turn_time = 30
        self.time_remaining = 30
        self.turn_number = 0
        self.used_count = 0
        self.is_my_turn = False

        # Chat/History
        self.history: list[dict] = []  # {player, city, color}
        self.opponent_typing = ""
        self.last_city = ""
        self.last_event = ""
        self.error_message = ""
        self.error_timer = 0

        # Visual
        self.particles = ParticleSystem()
        self.floating_texts: list[FloatingText] = []
        self.stars = [Star() for _ in range(150)]
        self.bg_hue_shift = 0
        self.pulse = 0
        self.screen_shake = 0
        self.transition_alpha = 255  # for screen transitions
        self.transition_dir = -1  # -1 = fading in, 1 = fading out

        # UI elements
        self.name_input = InputBox(SCREEN_W // 2 - 200, 400, 400, 50, "Введите имя...")
        self.name_input.active = True
        self.ip_input = InputBox(SCREEN_W // 2 - 200, 480, 300, 50, "IP сервера...")
        self.ip_input.text = "localhost"
        self.port_input = InputBox(SCREEN_W // 2 + 120, 480, 80, 50, "Порт")
        self.port_input.text = "5555"
        self.connect_btn = Button(SCREEN_W // 2 - 120, 560, 240, 55, "ПОДКЛЮЧИТЬСЯ", ACCENT)

        self.city_input = InputBox(60, SCREEN_H - 80, SCREEN_W - 200, 50, "Введите город...")
        self.send_btn = Button(SCREEN_W - 130, SCREEN_H - 80, 120, 50, "ОТПРАВИТЬ", GREEN)

        # Network thread
        self.net_thread = None
        self.running = True
        self.messages_queue: list[dict] = []
        self.msg_lock = threading.Lock()

        # Animations
        self.title_anim_time = 0
        self.letter_display_scale = 1.0
        self.timer_pulse = 0
        self.accepted_flash = 0
        self.history_scroll = 0

    def connect(self, host, port, name):
        """Подключение к серверу."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((host, int(port)))
            self.sock.settimeout(None)
            self.my_name = name
            send_message_sync(self.sock, {'type': 'join', 'name': name})

            # Запускаем поток приёмки
            self.net_thread = threading.Thread(target=self.network_loop, daemon=True)
            self.net_thread.start()
            self.state = 'connecting'
            return True
        except Exception as e:
            self.error_message = f"Ошибка подключения: {e}"
            self.error_timer = 4
            return False

    def network_loop(self):
        """Цикл получения сообщений от сервера."""
        while self.running:
            try:
                msg = recv_message_sync(self.sock)
                if msg is None:
                    with self.msg_lock:
                        self.messages_queue.append({'type': 'disconnected'})
                    break
                with self.msg_lock:
                    self.messages_queue.append(msg)
            except Exception as e:
                with self.msg_lock:
                    self.messages_queue.append({'type': 'disconnected', 'error': str(e)})
                break

    def send_typing(self):
        """Отправить текущий набираемый текст."""
        if self.sock and self.is_my_turn:
            try:
                send_message_sync(self.sock, {
                    'type': 'typing',
                    'text': self.city_input.text
                })
            except:
                pass

    def send_city(self, city: str):
        """Отправить город."""
        if self.sock and city.strip():
            try:
                send_message_sync(self.sock, {
                    'type': 'submit',
                    'city': city.strip()
                })
            except:
                pass

    def process_messages(self):
        """Обработать входящие сообщения."""
        with self.msg_lock:
            messages = self.messages_queue[:]
            self.messages_queue.clear()

        for msg in messages:
            msg_type = msg.get('type')

            if msg_type == 'wait':
                self.player_id = msg['player_id']
                self.state = 'waiting'
                self.last_event = msg['message']

            elif msg_type == 'game_start':
                self.state = 'playing'
                self.player_names = msg['players']
                self.current_player = msg['first_player']
                self.lives = msg.get('lives', [3, 3])
                self.last_event = msg['message']
                self.transition_alpha = 255
                self.transition_dir = -1
                self.particles.emit_confetti(80)
                self.floating_texts.append(FloatingText(
                    "ИГРА НАЧАЛАСЬ!",  # ✅ Русский
                    SCREEN_W // 2, SCREEN_H // 2 - 50,
                    GOLD, 56, 3.0
                ))

            elif msg_type == 'turn_start':
                self.current_player = msg['current_player']
                self.required_letter = msg.get('required_letter')
                self.turn_time = msg['turn_time']
                self.time_remaining = msg['turn_time']
                self.turn_number = msg['turn_number']
                self.scores = msg['scores']
                self.lives = msg.get('lives', self.lives)
                self.used_count = msg['used_count']
                self.is_my_turn = (msg['current_player'] == self.player_id)
                self.opponent_typing = ""
                self.city_input.active = self.is_my_turn
                self.city_input.glow_color = GREEN if self.is_my_turn else ACCENT

                if self.is_my_turn:
                    self.city_input.text = ""
                    self.particles.emit(SCREEN_W // 2, SCREEN_H // 2, 15, color=GREEN)

                if self.required_letter:
                    self.letter_display_scale = 2.0

            elif msg_type == 'timer_tick':
                self.time_remaining = msg['remaining']
                if self.time_remaining <= 5:
                    self.timer_pulse = 1.0

            elif msg_type == 'opponent_typing':
                self.opponent_typing = msg['text']

            elif msg_type == 'city_accepted':
                city = msg['city']
                player = msg['player']
                player_name = msg['player_name']
                self.scores = msg['scores']
                self.lives = msg.get('lives', self.lives)
                self.last_city = city

                color = GREEN if player == self.player_id else ACCENT
                self.history.append({
                    'player': player_name,
                    'city': city,
                    'color': color,
                    'time': time.time()
                })

                self.accepted_flash = 1.0
                cx, cy = SCREEN_W // 2, SCREEN_H // 2
                self.particles.emit_burst(cx, cy, 40,
                                         colors=[color, GOLD, WHITE])
                self.floating_texts.append(FloatingText(
                    f"✓ {city}",  # ✅ Символ ✓ работает!
                    cx, cy - 20, color, 42, 2.0
                ))

                pts = len(city)
                self.floating_texts.append(FloatingText(
                    f"+{pts} очков!",  # ✅ Русский
                    cx, cy + 30, GOLD, 32, 1.5
                ))

                if msg.get('no_cities_warning'):
                    self.floating_texts.append(FloatingText(
                        msg['warning_message'],
                        cx, cy + 70, RED, 28, 3.0
                    ))
                    self.screen_shake = 8

                self.opponent_typing = ""

            elif msg_type == 'city_rejected':
                self.error_message = msg['reason']
                self.error_timer = 3
                self.city_input.shake()
                self.screen_shake = 5
                self.particles.emit(SCREEN_W // 2, SCREEN_H - 100, 15, color=RED)
                self.floating_texts.append(FloatingText(
                    "✗ " + msg['reason'],  # ✅ Символ ✗ работает!
                    SCREEN_W // 2, SCREEN_H - 150,
                    RED, 30, 2.5
                ))

            elif msg_type == 'error':
                self.error_message = msg['message']
                self.error_timer = 3

            elif msg_type == 'timeout':
                player_idx = msg['player']
                player_name = msg['player_name']
                self.scores = msg['scores']
                self.lives = msg.get('lives', self.lives)
                new_letter = msg.get('new_letter')
                timeout_message = msg.get('message', f"Время вышло у {player_name}!")
                
                cx, cy = SCREEN_W // 2, SCREEN_H // 2
                
                self.floating_texts.append(FloatingText(
                    timeout_message,
                    cx, cy - 50,
                    RED, 38, 3.5
                ))
                
                self.floating_texts.append(FloatingText(
                    "-1 ЖИЗНЬ",  # ✅ Русский
                    cx, cy,
                    RED, 48, 3.0
                ))
                
                if new_letter:
                    self.floating_texts.append(FloatingText(
                        f"Новая буква: {new_letter}",  # ✅ Русский
                        cx, cy + 50,
                        ACCENT, 36, 3.0
                    ))
                    self.letter_display_scale = 2.5
                
                self.screen_shake = 15
                self.particles.emit_burst(cx, cy, 80,
                                         colors=[RED, (255, 100, 0), (150, 0, 0)])

            elif msg_type == 'game_over':
                self.state = 'game_over'
                self.last_event = msg.get('reason', 'Игра окончена!')
                self.scores = msg.get('scores', self.scores)
                self.lives = msg.get('lives', self.lives)
                winner = msg.get('winner', -1)
                
                # Определяем, победили ли мы
                if winner == self.player_id:
                    self.floating_texts.append(FloatingText(
                        "ВЫ ПОБЕДИЛИ!",  # ✅ Русский
                        SCREEN_W // 2, SCREEN_H // 2 - 100,
                        GOLD, 64, 5.0
                    ))
                    self.particles.emit_confetti(300)
                elif winner == -1:
                    self.floating_texts.append(FloatingText(
                        "НИЧЬЯ!",  # ✅ Русский
                        SCREEN_W // 2, SCREEN_H // 2 - 100,
                        GRAY, 64, 5.0
                    ))
                else:
                    self.floating_texts.append(FloatingText(
                        "ВЫ ПРОИГРАЛИ...",  # ✅ Русский
                        SCREEN_W // 2, SCREEN_H // 2 - 100,
                        RED, 64, 5.0
                    ))

            elif msg_type == 'disconnected':
                if self.state != 'game_over':
                    self.state = 'menu'
                    self.error_message = "Соединение потеряно!"  # ✅ Русский
                    self.error_timer = 5

    # ============================================================
    # DRAWING
    # ============================================================

    def draw_background(self, t):
        """Красивый анимированный фон."""
        # Gradient
        for y in range(SCREEN_H):
            ratio = y / SCREEN_H
            r = int(BG_GRADIENT_TOP[0] * (1 - ratio) + BG_GRADIENT_BOT[0] * ratio)
            g = int(BG_GRADIENT_TOP[1] * (1 - ratio) + BG_GRADIENT_BOT[1] * ratio)
            b = int(BG_GRADIENT_TOP[2] * (1 - ratio) + BG_GRADIENT_BOT[2] * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (SCREEN_W, y))

        # Stars
        for star in self.stars:
            star.update(1 / 60, t)
            star.draw(self.screen)

        # Subtle moving aurora
        aurora_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for i in range(3):
            cx = SCREEN_W // 2 + math.sin(t * 0.3 + i * 2) * 300
            cy = 150 + math.cos(t * 0.2 + i) * 50
            radius = 250 + math.sin(t * 0.5 + i) * 50
            colors = [(0, 100, 200, 8), (100, 0, 200, 6), (0, 200, 100, 5)]
            pygame.draw.circle(aurora_surf, colors[i], (int(cx), int(cy)), int(radius))
        self.screen.blit(aurora_surf, (0, 0))

    def draw_panel(self, rect, alpha=200, border_color=DARK_GRAY):
        """Нарисовать стеклянную панель."""
        panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        panel.fill((*BG_DARK, alpha))
        # Inner highlight
        pygame.draw.rect(panel, (255, 255, 255, 10), (0, 0, rect.w, rect.h // 3))
        self.screen.blit(panel, rect.topleft)
        pygame.draw.rect(self.screen, border_color, rect, 1, border_radius=8)

    def draw_timer_bar(self, x, y, w, h):
        """Красивый таймер."""
        ratio = max(0, self.time_remaining / self.turn_time) if self.turn_time > 0 else 0
        # Background
        pygame.draw.rect(self.screen, DARK_GRAY, (x, y, w, h), border_radius=h // 2)

        # Fill
        fill_w = int(w * ratio)
        if fill_w > 0:
            if ratio > 0.5:
                color = GREEN
            elif ratio > 0.25:
                color = GOLD
            else:
                color = RED
                # Pulsing when low
                pulse = abs(math.sin(time.time() * 6))
                color = tuple(int(c * (0.5 + 0.5 * pulse)) for c in color)

            pygame.draw.rect(self.screen, color, (x, y, fill_w, h), border_radius=h // 2)

            # Shine
            shine = pygame.Surface((fill_w, h // 2), pygame.SRCALPHA)
            shine.fill((255, 255, 255, 40))
            self.screen.blit(shine, (x, y))

        # Time text
        time_text = f"{self.time_remaining:.0f}с"
        text_surf = self.font_medium.render(time_text, True, WHITE)
        self.screen.blit(text_surf, text_surf.get_rect(center=(x + w // 2, y + h // 2)))

    def draw_required_letter(self, x, y):
        """Большая анимированная буква."""
        if not self.required_letter:
            return

        # Animate scale
        if self.letter_display_scale > 1.0:
            self.letter_display_scale = max(1.0, self.letter_display_scale - 0.03)

        scale = self.letter_display_scale
        pulse = 1 + 0.05 * math.sin(time.time() * 3)
        final_scale = scale * pulse

        font_size = int(80 * final_scale)
        font = pygame.font.Font(None, font_size)

        # Glow
        glow_surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        glow_r = int(60 * final_scale)
        pygame.draw.circle(glow_surf, (*ACCENT, 30), (100, 100), glow_r)
        pygame.draw.circle(glow_surf, (*ACCENT, 15), (100, 100), glow_r + 20)
        self.screen.blit(glow_surf, (x - 100, y - 100))

        # Letter
        letter_surf = font.render(self.required_letter, True, ACCENT)
        rect = letter_surf.get_rect(center=(x, y))
        self.screen.blit(letter_surf, rect)

        # Label
        label = self.font_small.render("Следующая буква", True, GRAY)
        self.screen.blit(label, label.get_rect(center=(x, y + 55)))

    def draw_scores(self, x, y):
        """Панель счёта."""
        panel_rect = pygame.Rect(x, y, 280, 120)
        self.draw_panel(panel_rect, 180)

        title = self.font_medium.render("⭐ СЧЁТ", True, GOLD)
        self.screen.blit(title, title.get_rect(center=(x + 140, y + 25)))

        for i in range(2):
            name = self.player_names[i] if i < len(self.player_names) else f"Игрок {i + 1}"
            score = self.scores[i] if i < len(self.scores) else 0
            is_me = (i == self.player_id)
            color = GREEN if is_me else ACCENT
            marker = " (Вы)" if is_me else ""

            text = f"{name}{marker}: {score}"
            surf = self.font_small.render(text, True, color)
            self.screen.blit(surf, (x + 15, y + 50 + i * 30))
    
    def draw_lives(self, x, y):
        """Панель жизней с сердечками."""
        panel_rect = pygame.Rect(x, y, 280, 100)
        self.draw_panel(panel_rect, 180)

        title = self.font_medium.render("💖 ЖИЗНИ", True, RED)
        self.screen.blit(title, title.get_rect(center=(x + 140, y + 25)))

        for i in range(2):
            name = self.player_names[i] if i < len(self.player_names) else f"Игрок {i + 1}"
            lives_count = self.lives[i] if i < len(self.lives) else 3
            is_me = (i == self.player_id)
            
            # Рисуем сердечки
            hearts_x = x + 15
            hearts_y = y + 55 + i * 35
            
            name_color = GREEN if is_me else ACCENT
            name_surf = self.font_tiny.render(name[:12], True, name_color)
            self.screen.blit(name_surf, (hearts_x, hearts_y - 2))
            
            # Сердечки с пульсацией
            pulse = 1 + 0.1 * math.sin(time.time() * 3 + i)
            heart_size = int(20 * pulse) if lives_count > 0 else 20
            
            for h in range(3):
                hx = hearts_x + 120 + h * 35
                if h < lives_count:
                    # Живое сердце
                    heart_color = RED
                    heart_font = pygame.font.Font(None, heart_size)
                    heart = heart_font.render("♥", True, heart_color)
                    
                    # Glow эффект
                    glow_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
                    pygame.draw.circle(glow_surf, (*RED, 30), (20, 20), 15)
                    self.screen.blit(glow_surf, (hx - 10, hearts_y - 10))
                    
                    self.screen.blit(heart, heart.get_rect(center=(hx, hearts_y)))
                else:
                    # Потерянное сердце
                    empty_heart = self.font_medium.render("♡", True, DARK_GRAY)
                    self.screen.blit(empty_heart, empty_heart.get_rect(center=(hx, hearts_y)))

    def draw_lives_on(self, surface, x, y):
        """Панель жизней с сердечками."""
        panel = pygame.Surface((280, 100), pygame.SRCALPHA)
        panel.fill((*BG_DARK, 180))
        surface.blit(panel, (x, y))
        pygame.draw.rect(surface, DARK_GRAY, (x, y, 280, 100), 1, border_radius=8)

        title = self.font_medium.render("ЖИЗНИ", True, RED)  # ✅ Русский
        surface.blit(title, title.get_rect(center=(x + 140, y + 25)))

        for i in range(2):
            name = self.player_names[i] if i < len(self.player_names) else f"Игрок {i + 1}"
            lives_count = self.lives[i] if i < len(self.lives) else 3
            is_me = (i == self.player_id)
            
            hearts_x = x + 15
            hearts_y = y + 55 + i * 35
            
            name_color = GREEN if is_me else ACCENT
            name_surf = self.font_tiny.render(name[:12], True, name_color)
            surface.blit(name_surf, (hearts_x, hearts_y - 2))
            
            # Рисуем сердечки графически (кружочками)
            for h in range(3):
                hx = hearts_x + 120 + h * 30
                if h < lives_count:
                    # Живое сердце - красный круг с пульсацией
                    pulse = 1 + 0.15 * math.sin(time.time() * 3 + i + h * 0.5)
                    radius = int(8 * pulse)
                    
                    # Glow
                    glow_surf = pygame.Surface((30, 30), pygame.SRCALPHA)
                    pygame.draw.circle(glow_surf, (*RED, 40), (15, 15), radius + 5)
                    surface.blit(glow_surf, (hx - 15, hearts_y - 15))
                    
                    # Само сердце (круг)
                    pygame.draw.circle(surface, RED, (hx, hearts_y), radius)
                    pygame.draw.circle(surface, (255, 150, 150), (hx, hearts_y), max(1, radius - 2))
                else:
                    # Потерянное сердце - серый контур
                    pygame.draw.circle(surface, DARK_GRAY, (hx, hearts_y), 6, 2)

    def draw_history(self, x, y, w, h):
        """История названных городов."""
        panel_rect = pygame.Rect(x, y, w, h)
        self.draw_panel(panel_rect, 160)

        title = self.font_small.render("📜 История городов", True, GRAY)
        self.screen.blit(title, (x + 10, y + 8))

        # Scrollable list
        clip_rect = pygame.Rect(x + 5, y + 35, w - 10, h - 45)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        visible_items = (h - 45) // 28
        start = max(0, len(self.history) - visible_items)

        for idx, entry in enumerate(self.history[start:]):
            ey = y + 38 + idx * 28
            if ey > y + h - 10:
                break

            # Fade-in animation
            age = time.time() - entry.get('time', 0)
            alpha = min(255, int(age * 500))

            city_text = f"{entry['player']}: {entry['city']}"
            surf = self.font_tiny.render(city_text, True, entry['color'])
            surf.set_alpha(alpha)
            self.screen.blit(surf, (x + 15, ey))

            # Number
            num = self.font_tiny.render(f"{start + idx + 1}.", True, DARK_GRAY)
            num.set_alpha(alpha)
            self.screen.blit(num, (x + 3, ey))

        self.screen.set_clip(old_clip)

    def draw_opponent_typing(self, x, y):
        """Показать, что печатает соперник."""
        if not self.opponent_typing or self.is_my_turn:
            return

        # Animated dots
        dots = "." * (int(time.time() * 3) % 4)
        text = f"Соперник печатает: {self.opponent_typing}{dots}"
        surf = self.font_small.render(text, True, ACCENT2)

        # Background
        bg_rect = pygame.Rect(x - 5, y - 5, surf.get_width() + 10, surf.get_height() + 10)
        bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
        bg.fill((*BG_DARK, 180))
        self.screen.blit(bg, bg_rect.topleft)
        pygame.draw.rect(self.screen, ACCENT2, bg_rect, 1, border_radius=5)

        self.screen.blit(surf, (x, y))

    def draw_turn_indicator(self, x, y):
        """Индикатор чьего хода."""
        if self.is_my_turn:
            text = "🎯 ВАШ ХОД!"
            color = GREEN
            # Particles trail
            if random.random() < 0.3:
                self.particles.emit_trail(x + random.randint(0, 200), y + 15, GREEN)
        else:
            opponent = self.player_names[1 - self.player_id] if len(self.player_names) > 1 else "Соперник"
            text = f"⏳ Ход: {opponent}"
            color = ACCENT

        pulse = 1 + 0.1 * math.sin(time.time() * 4)
        font_size = int(36 * pulse) if self.is_my_turn else 32
        font = pygame.font.Font(None, font_size)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(x, y))

        # Glow behind
        if self.is_my_turn:
            glow = pygame.Surface((rect.w + 30, rect.h + 20), pygame.SRCALPHA)
            glow.fill((*GREEN, 20))
            self.screen.blit(glow, (rect.x - 15, rect.y - 10))

        self.screen.blit(surf, rect)

    def draw_menu(self, t):
        """Экран меню."""
        self.draw_background(t)

        # Title with wave effect
        title_text = "ГОРОДА РОССИИ"
        total_w = 0
        char_surfs = []
        for i, ch in enumerate(title_text):
            offset_y = math.sin(t * 3 + i * 0.5) * 8
            color_shift = int(128 + 127 * math.sin(t * 2 + i * 0.3))
            color = (color_shift, 200, 255)
            surf = self.font_title.render(ch, True, color)
            char_surfs.append((surf, offset_y))
            total_w += surf.get_width()

        start_x = SCREEN_W // 2 - total_w // 2
        for surf, oy in char_surfs:
            self.screen.blit(surf, (start_x, 150 + oy))
            start_x += surf.get_width()

        # Subtitle
        sub = self.font_medium.render("Сетевая игра по LAN", True, GRAY)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W // 2, 240)))

        # Decorative line
        line_w = 300 + math.sin(t * 2) * 50
        pygame.draw.line(self.screen, ACCENT,
                        (SCREEN_W // 2 - line_w // 2, 270),
                        (SCREEN_W // 2 + line_w // 2, 270), 2)

        # Labels
        name_label = self.font_small.render("Ваше имя:", True, WHITE)
        self.screen.blit(name_label, (SCREEN_W // 2 - 200, 375))

        server_label = self.font_small.render("Сервер:", True, WHITE)
        self.screen.blit(server_label, (SCREEN_W // 2 - 200, 455))

        # Input fields & button
        self.name_input.draw(self.screen)
        self.ip_input.draw(self.screen)
        self.port_input.draw(self.screen)
        self.connect_btn.draw(self.screen)

        # Info
        info_lines = [
            "📌 Запустите server.py на одном компьютере",
            "📌 Подключитесь двумя клиентами",
            "📌 Называйте города России по очереди!",
        ]
        for i, line in enumerate(info_lines):
            surf = self.font_tiny.render(line, True, GRAY)
            self.screen.blit(surf, surf.get_rect(center=(SCREEN_W // 2, 650 + i * 25)))

        # Error
        if self.error_timer > 0:
            err_surf = self.font_medium.render(self.error_message, True, RED)
            err_surf.set_alpha(int(255 * min(1, self.error_timer)))
            self.screen.blit(err_surf, err_surf.get_rect(center=(SCREEN_W // 2, 620)))

        # Ambient particles
        if random.random() < 0.1:
            self.particles.emit_trail(
                random.randint(0, SCREEN_W),
                random.randint(0, SCREEN_H),
                random.choice([ACCENT, ACCENT2])
            )

    def draw_waiting(self, t):
        """Экран ожидания."""
        self.draw_background(t)

        # Spinning loader
        cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 30
        radius = 40
        for i in range(12):
            angle = t * 3 + i * (2 * math.pi / 12)
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            alpha = int(255 * (i / 12))
            size = 4 + (i / 12) * 4
            dot_surf = pygame.Surface((int(size * 2), int(size * 2)), pygame.SRCALPHA)
            pygame.draw.circle(dot_surf, (*ACCENT, alpha), (int(size), int(size)), int(size))
            self.screen.blit(dot_surf, (x - size, y - size))

        text = self.font_large.render("Ожидание игрока...", True, WHITE)
        self.screen.blit(text, text.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 50)))

        sub = self.font_small.render(self.last_event, True, GRAY)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 90)))

    def draw_playing(self, t):
        """Основной игровой экран."""
        self.draw_background(t)

        shake_x, shake_y = 0, 0
        if self.screen_shake > 0:
            shake_x = int(math.sin(t * 50) * self.screen_shake)
            shake_y = int(math.cos(t * 47) * self.screen_shake * 0.5)
            self.screen_shake *= 0.92
            if self.screen_shake < 0.5:
                self.screen_shake = 0

        game_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        # Top bar
        top_panel = pygame.Rect(0, 0, SCREEN_W, 70)
        panel_s = pygame.Surface((SCREEN_W, 70), pygame.SRCALPHA)
        panel_s.fill((15, 15, 40, 220))
        game_surf.blit(panel_s, (0, 0))

        turn_text = f"Ход #{self.turn_number}"
        turn_surf = self.font_small.render(turn_text, True, GRAY)
        game_surf.blit(turn_surf, (20, 10))

        used_text = f"Городов названо: {self.used_count + len(self.history)}"
        used_surf = self.font_tiny.render(used_text, True, GRAY)
        game_surf.blit(used_surf, (20, 40))

        # Timer bar
        self.draw_timer_bar_on(game_surf, SCREEN_W // 2 - 200, 15, 400, 35)

        # Turn indicator
        self.draw_turn_indicator_on(game_surf, SCREEN_W // 2, 95)

        # Required letter (center)
        self.draw_required_letter_on(game_surf, SCREEN_W // 2, 180)

        # Scores (top right)
        self.draw_scores_on(game_surf, SCREEN_W - 300, 80)
        
        # 🆕 Lives (под очками)
        self.draw_lives_on(game_surf, SCREEN_W - 300, 210)

        # History (left panel) — сдвигаем вниз
        self.draw_history_on(game_surf, 20, 120, 280, SCREEN_H - 240)

        # Last city display
        if self.last_city:
            city_font = pygame.font.Font(None, 52)
            city_surf = city_font.render(self.last_city, True, GOLD)
            pulse_scale = 1 + 0.02 * math.sin(t * 2)
            scaled = pygame.transform.rotozoom(city_surf, 0, pulse_scale)
            game_surf.blit(scaled, scaled.get_rect(center=(SCREEN_W // 2, 290)))

            label = self.font_tiny.render("Последний город", True, GRAY)
            game_surf.blit(label, label.get_rect(center=(SCREEN_W // 2, 320)))

        # Opponent typing
        if self.opponent_typing and not self.is_my_turn:
            self.draw_opponent_typing_on(game_surf, 320, SCREEN_H - 140)

        # Input area
        input_panel = pygame.Surface((SCREEN_W, 100), pygame.SRCALPHA)
        input_panel.fill((15, 15, 40, 220))
        game_surf.blit(input_panel, (0, SCREEN_H - 100))

        if not self.is_my_turn:
            waiting_text = "Ожидание хода соперника..."
            w_surf = self.font_medium.render(waiting_text, True, GRAY)
            game_surf.blit(w_surf, w_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H - 50)))

        if self.error_timer > 0:
            err_surf = self.font_medium.render(self.error_message, True, RED)
            alpha = int(255 * min(1, self.error_timer))
            err_surf.set_alpha(alpha)
            game_surf.blit(err_surf, err_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H - 130)))

        if self.accepted_flash > 0:
            flash = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            flash.fill((*GREEN, int(30 * self.accepted_flash)))
            game_surf.blit(flash, (0, 0))
            self.accepted_flash -= 0.03

        self.screen.blit(game_surf, (shake_x, shake_y))

        if self.is_my_turn:
            self.city_input.draw(self.screen)
            self.send_btn.draw(self.screen)

    def draw_timer_bar_on(self, surface, x, y, w, h):
        ratio = max(0, self.time_remaining / self.turn_time) if self.turn_time > 0 else 0
        pygame.draw.rect(surface, DARK_GRAY, (x, y, w, h), border_radius=h // 2)
        fill_w = int(w * ratio)
        if fill_w > 0:
            if ratio > 0.5:
                color = GREEN
            elif ratio > 0.25:
                color = GOLD
            else:
                color = RED
                pulse = abs(math.sin(time.time() * 6))
                color = tuple(int(c * (0.5 + 0.5 * pulse)) for c in color)
            pygame.draw.rect(surface, color, (x, y, fill_w, h), border_radius=h // 2)
            shine = pygame.Surface((fill_w, h // 2), pygame.SRCALPHA)
            shine.fill((255, 255, 255, 40))
            surface.blit(shine, (x, y))
        time_text = f"{self.time_remaining:.0f}с"
        text_surf = self.font_medium.render(time_text, True, WHITE)
        surface.blit(text_surf, text_surf.get_rect(center=(x + w // 2, y + h // 2)))

    def draw_turn_indicator_on(self, surface, x, y):
        if self.is_my_turn:
            text = "ВАШ ХОД!"  # ✅ Русский
            color = GREEN
        else:
            opponent = self.player_names[1 - self.player_id] if len(self.player_names) > 1 else "Соперник"
            text = f"Ход: {opponent}"  # ✅ Русский
            color = ACCENT
        pulse = 1 + 0.1 * math.sin(time.time() * 4) if self.is_my_turn else 1
        font_size = int(36 * pulse) if self.is_my_turn else 32
        font = pygame.font.Font(None, font_size)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(x, y))
        if self.is_my_turn:
            glow = pygame.Surface((rect.w + 30, rect.h + 20), pygame.SRCALPHA)
            glow.fill((*GREEN, 20))
            surface.blit(glow, (rect.x - 15, rect.y - 10))
        surface.blit(surf, rect)

    def draw_required_letter_on(self, surface, x, y):
        if not self.required_letter:
            label = self.font_medium.render("Любой город!", True, ACCENT)
            surface.blit(label, label.get_rect(center=(x, y)))
            return
        if self.letter_display_scale > 1.0:
            self.letter_display_scale = max(1.0, self.letter_display_scale - 0.03)
        scale = self.letter_display_scale
        pulse = 1 + 0.05 * math.sin(time.time() * 3)
        final_scale = scale * pulse
        font_size = int(80 * final_scale)
        font = pygame.font.Font(None, max(10, font_size))
        glow_surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        glow_r = int(60 * final_scale)
        pygame.draw.circle(glow_surf, (*ACCENT, 30), (100, 100), glow_r)
        pygame.draw.circle(glow_surf, (*ACCENT, 15), (100, 100), glow_r + 20)
        surface.blit(glow_surf, (x - 100, y - 100))
        letter_surf = font.render(self.required_letter, True, ACCENT)
        rect = letter_surf.get_rect(center=(x, y))
        surface.blit(letter_surf, rect)
        label = self.font_small.render("Город на букву:", True, GRAY)
        surface.blit(label, label.get_rect(center=(x, y - 55)))

    def draw_scores_on(self, surface, x, y):
        """Панель счёта."""
        panel_rect = pygame.Rect(x, y, 280, 120)
        panel = pygame.Surface((280, 120), pygame.SRCALPHA)
        panel.fill((*BG_DARK, 180))
        surface.blit(panel, (x, y))
        pygame.draw.rect(surface, DARK_GRAY, panel_rect, 1, border_radius=8)
        
        title = self.font_medium.render("СЧЁТ", True, GOLD)  # ✅ Русский
        surface.blit(title, title.get_rect(center=(x + 140, y + 25)))
        
        for i in range(2):
            name = self.player_names[i] if i < len(self.player_names) else f"Игрок {i + 1}"
            score = self.scores[i] if i < len(self.scores) else 0
            is_me = (i == self.player_id)
            color = GREEN if is_me else ACCENT
            marker = " (Вы)" if is_me else ""
            text = f"{name}{marker}: {score}"
            surf = self.font_small.render(text, True, color)
            surface.blit(surf, (x + 15, y + 50 + i * 30))

    def draw_history_on(self, surface, x, y, w, h):
        """История названных городов."""
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((*BG_DARK, 160))
        surface.blit(panel, (x, y))
        pygame.draw.rect(surface, DARK_GRAY, (x, y, w, h), 1, border_radius=8)
        
        title = self.font_small.render("История городов", True, GRAY)  # ✅ Русский
        surface.blit(title, (x + 10, y + 8))

        visible_items = (h - 45) // 26
        start = max(0, len(self.history) - visible_items)
        for idx, entry in enumerate(self.history[start:]):
            ey = y + 38 + idx * 26
            if ey > y + h - 10:
                break
            age = time.time() - entry.get('time', 0)
            alpha = min(255, int(age * 500))
            num_text = f"{start + idx + 1}."
            num_surf = self.font_tiny.render(num_text, True, DARK_GRAY)
            num_surf.set_alpha(alpha)
            surface.blit(num_surf, (x + 5, ey))
            city_text = f"{entry['player']}: {entry['city']}"
            if len(city_text) > 28:
                city_text = city_text[:25] + "..."
            ct_surf = self.font_tiny.render(city_text, True, entry['color'])
            ct_surf.set_alpha(alpha)
            surface.blit(ct_surf, (x + 30, ey))


    def draw_opponent_typing_on(self, surface, x, y):
        if not self.opponent_typing or self.is_my_turn:
            return
        dots = "." * (int(time.time() * 3) % 4)
        text = f"Соперник: {self.opponent_typing}{dots}"
        surf = self.font_small.render(text, True, ACCENT2)
        bg_rect = pygame.Rect(x - 5, y - 5, surf.get_width() + 10, surf.get_height() + 10)
        bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
        bg.fill((*BG_DARK, 180))
        surface.blit(bg, bg_rect.topleft)
        pygame.draw.rect(surface, ACCENT2, bg_rect, 1, border_radius=5)
        surface.blit(surf, (x, y))

    def draw_game_over(self, t):
        """Экран окончания игры."""
        self.draw_background(t)

        # Title
        title = self.font_title.render("ИГРА ОКОНЧЕНА!", True, GOLD)  # ✅ Русский
        pulse = 1 + 0.05 * math.sin(t * 3)
        scaled = pygame.transform.rotozoom(title, 0, pulse)
        self.screen.blit(scaled, scaled.get_rect(center=(SCREEN_W // 2, 150)))

        # Reason
        reason_surf = self.font_medium.render(self.last_event, True, WHITE)
        self.screen.blit(reason_surf, reason_surf.get_rect(center=(SCREEN_W // 2, 230)))

        # Scores panel
        panel_rect = pygame.Rect(SCREEN_W // 2 - 300, 280, 600, 250)
        self.draw_panel(panel_rect, 200)

        # Жизни и счёт
        for i in range(2):
            name = self.player_names[i] if i < len(self.player_names) else f"Игрок {i + 1}"
            score = self.scores[i] if i < len(self.scores) else 0
            lives_count = self.lives[i] if i < len(self.lives) else 0
            is_me = (i == self.player_id)
            is_winner = lives_count > 0 if any(l > 0 for l in self.lives) else score == max(self.scores)

            color = GOLD if is_winner else GRAY
            marker = " [ПОБЕДИТЕЛЬ]" if is_winner else ""  # ✅ Русский
            me_marker = " (Вы)" if is_me else ""

            name_surf = self.font_large.render(f"{name}{me_marker}{marker}", True, color)
            score_surf = self.font_title.render(f"{score} очков", True, color)  # ✅ Русский
            lives_surf = self.font_medium.render(f"Жизней: {lives_count}", True, RED if lives_count > 0 else DARK_GRAY)  # ✅ Русский

            y_pos = 320 + i * 110
            self.screen.blit(name_surf, name_surf.get_rect(center=(SCREEN_W // 2, y_pos)))
            self.screen.blit(score_surf, score_surf.get_rect(center=(SCREEN_W // 2, y_pos + 40)))
            self.screen.blit(lives_surf, lives_surf.get_rect(center=(SCREEN_W // 2, y_pos + 75)))

        # Continuous confetti
        if random.random() < 0.2:
            self.particles.emit_confetti(5)

        # History summary
        summary = self.font_small.render(
            f"Всего городов названо: {len(self.history)}", True, GRAY)  # ✅ Русский
        self.screen.blit(summary, summary.get_rect(center=(SCREEN_W // 2, 570)))

    # ============================================================
    # MAIN LOOP
    # ============================================================
    def run(self):
        t = 0
        last_typing_text = ""

        while self.running:
            dt = self.clock.tick(FPS) / 1000
            t += dt

            # Events
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    if self.sock:
                        try:
                            send_message_sync(self.sock, {'type': 'disconnect'})
                            self.sock.close()
                        except:
                            pass
                    break

                if self.state == 'menu':
                    self.name_input.handle_event(event)
                    self.ip_input.handle_event(event)
                    self.port_input.handle_event(event)
                    if self.connect_btn.is_clicked(event):
                        name = self.name_input.text.strip() or "Игрок"
                        ip = self.ip_input.text.strip() or "localhost"
                        port = self.port_input.text.strip() or "5555"
                        self.connect(ip, port, name)

                elif self.state == 'playing':
                    if self.is_my_turn:
                        result = self.city_input.handle_event(event)
                        if result:
                            self.send_city(result)
                        if self.send_btn.is_clicked(event) and self.city_input.text:
                            self.send_city(self.city_input.text)
                            self.city_input.text = ""

            if not self.running:
                break

            # Process network messages
            self.process_messages()

            # Update UI
            self.name_input.update(dt)
            self.ip_input.update(dt)
            self.port_input.update(dt)
            self.city_input.update(dt)
            self.connect_btn.update(mouse_pos, dt)
            self.send_btn.update(mouse_pos, dt)
            self.particles.update(dt)
            self.floating_texts = [ft for ft in self.floating_texts if ft.update(dt)]

            if self.error_timer > 0:
                self.error_timer -= dt

            # Send typing updates
            if self.state == 'playing' and self.is_my_turn:
                if self.city_input.text != last_typing_text:
                    last_typing_text = self.city_input.text
                    self.send_typing()

            # Transition
            if self.transition_alpha > 0 and self.transition_dir == -1:
                self.transition_alpha = max(0, self.transition_alpha - int(dt * 400))

            # Draw
            self.screen.fill(BG_DARK)

            if self.state == 'menu':
                self.draw_menu(t)
            elif self.state in ('connecting', 'waiting'):
                self.draw_waiting(t)
            elif self.state == 'playing':
                self.draw_playing(t)
            elif self.state == 'game_over':
                self.draw_game_over(t)

            # Particles & floating text (on top)
            self.particles.draw(self.screen)
            for ft in self.floating_texts:
                ft.draw(self.screen)

            # Screen transition overlay
            if self.transition_alpha > 0:
                overlay = pygame.Surface((SCREEN_W, SCREEN_H))
                overlay.fill(BG_DARK)
                overlay.set_alpha(self.transition_alpha)
                self.screen.blit(overlay, (0, 0))

            pygame.display.flip()

        pygame.quit()
        sys.exit()


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == '__main__':
    client = GameClient()
    client.run()