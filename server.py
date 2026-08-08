"""
Сервер игры "Города России" с системой жизней.
Запуск: python server.py [port]
"""
import socket
import threading
import time
import random
import sys
import traceback
from cities_db import (RUSSIAN_CITIES, CITIES_SET, CITIES_BY_LETTER,
                       get_required_letter, normalize)
from protocol import send_message_sync, recv_message_sync


class GameServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.players: list[socket.socket] = []
        self.player_names: list[str] = []
        self.used_cities: set[str] = set()
        self.current_player = 0
        self.required_letter: str | None = None
        self.turn_number = 0
        self.scores = [0, 0]
        self.lives = [3, 3]
        self.running = True
        self.turn_time = 30
        self.lock = threading.Lock()
        self.game_ended = False  # 🆕 флаг завершения игры

    def broadcast(self, data: dict, exclude=-1):
        for i, sock in enumerate(self.players):
            if i != exclude:
                try:
                    send_message_sync(sock, data)
                except Exception as e:
                    print(f"[СЕРВЕР] Ошибка отправки игроку {i}: {e}")

    def send_to(self, player_idx: int, data: dict):
        try:
            send_message_sync(self.players[player_idx], data)
        except Exception as e:
            print(f"[СЕРВЕР] Ошибка отправки игроку {player_idx}: {e}")

    def get_turn_time(self):
        """30 секунд первые 10 ходов, потом 15."""
        if self.turn_number < 10:
            return 30
        return 15

    def listen_for_typing(self, player_idx: int):
        """Слушаем события набора текста от игрока в отдельном потоке."""
        sock = self.players[player_idx]
        while self.running and not self.game_ended:
            try:
                msg = recv_message_sync(sock)
                if msg is None:
                    if not self.game_ended:  # 🆕 только если игра не закончилась
                        print(f"[СЕРВЕР] Игрок {player_idx} отключился")
                        self.running = False
                    break
                if msg.get('type') == 'typing':
                    other = 1 - player_idx
                    self.send_to(other, {
                        'type': 'opponent_typing',
                        'text': msg['text']
                    })
                elif msg.get('type') == 'submit':
                    with self.lock:
                        if hasattr(self, '_pending_answer') and self._pending_answer is None:
                            self._pending_answer = (player_idx, msg['city'])
                elif msg.get('type') == 'disconnect':
                    if not self.game_ended:
                        print(f"[СЕРВЕР] Игрок {player_idx} вышел из игры")
                        self.running = False
                    break
            except Exception as e:
                if not self.game_ended:
                    print(f"[СЕРВЕР] Ошибка в listen_for_typing для игрока {player_idx}: {e}")
                    self.running = False
                break

    def validate_city(self, city: str, player_idx: int) -> tuple[bool, str]:
        """Проверить валидность города. Возвращает (ok, reason)."""
        norm = normalize(city)

        if norm not in CITIES_SET:
            return False, f"'{city}' - нет такого города в базе!"

        if norm in self.used_cities:
            return False, f"'{city}' уже был назван!"

        if self.required_letter:
            first_letter = city[0].upper()
            if first_letter != self.required_letter:
                return False, f"Город должен начинаться на букву '{self.required_letter}'!"

        return True, "OK"

    def find_original_name(self, norm: str) -> str:
        """Найти оригинальное написание города."""
        for c in RUSSIAN_CITIES:
            if normalize(c) == norm:
                return c
        return norm.title()

    def check_available_cities(self, letter: str) -> list[str]:
        """Проверить, есть ли доступные города на букву."""
        available = []
        for c in CITIES_BY_LETTER.get(letter, []):
            if normalize(c) not in self.used_cities:
                available.append(c)
        return available

    def get_random_letter(self) -> str:
        """Получить случайную букву, на которую есть города."""
        available_letters = []
        for letter, cities in CITIES_BY_LETTER.items():
            if any(normalize(c) not in self.used_cities for c in cities):
                available_letters.append(letter)
        
        if available_letters:
            return random.choice(available_letters)
        return None

    def end_game(self, reason: str, winner: int = -1):
        """Завершить игру корректно."""
        self.game_ended = True
        self.running = False
        
        print(f"[СЕРВЕР] Игра завершена: {reason}")
        
        self.broadcast({
            'type': 'game_over',
            'reason': reason,
            'winner': winner,
            'scores': self.scores,
            'lives': self.lives,
            'players': self.player_names
        })
        
        time.sleep(2)  # даём время клиентам получить сообщение

    def run(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(2)
        print(f"[СЕРВЕР] Запущен на {self.host}:{self.port}")
        print("[СЕРВЕР] Ожидание игроков...")

        try:
            while len(self.players) < 2:
                conn, addr = server_sock.accept()
                msg = recv_message_sync(conn)
                if msg and msg.get('type') == 'join':
                    name = msg.get('name', f'Игрок {len(self.players) + 1}')
                    self.players.append(conn)
                    self.player_names.append(name)
                    print(f"[СЕРВЕР] Подключился: {name} ({addr})")
                    send_message_sync(conn, {
                        'type': 'wait',
                        'message': f'Добро пожаловать, {name}! Ожидание второго игрока...',
                        'player_id': len(self.players) - 1
                    })

            print("[СЕРВЕР] Оба игрока подключены. Старт игры!")
            time.sleep(0.5)

            self.current_player = random.randint(0, 1)

            self.broadcast({
                'type': 'game_start',
                'players': self.player_names,
                'first_player': self.current_player,
                'lives': self.lives,
                'message': f'Игра начинается! Первым ходит {self.player_names[self.current_player]}'
            })

            listeners = []
            for i in range(2):
                t = threading.Thread(target=self.listen_for_typing, args=(i,), daemon=True)
                t.start()
                listeners.append(t)

            time.sleep(2)
            self.game_loop()
            
        except Exception as e:
            print(f"[СЕРВЕР] Критическая ошибка: {e}")
            traceback.print_exc()
        finally:
            for sock in self.players:
                try:
                    sock.close()
                except:
                    pass
            server_sock.close()
            print("[СЕРВЕР] Сервер остановлен.")

    def game_loop(self):
        try:
            while self.running and not self.game_ended:
                # Проверка на проигрыш
                if self.lives[0] <= 0:
                    self.end_game(f'{self.player_names[1]} победил!', winner=1)
                    return
                
                if self.lives[1] <= 0:
                    self.end_game(f'{self.player_names[0]} победил!', winner=0)
                    return

                turn_time = self.get_turn_time()
                self.turn_number += 1

                self.broadcast({
                    'type': 'turn_start',
                    'current_player': self.current_player,
                    'player_name': self.player_names[self.current_player],
                    'required_letter': self.required_letter,
                    'turn_time': turn_time,
                    'turn_number': self.turn_number,
                    'scores': self.scores,
                    'lives': self.lives,
                    'used_count': len(self.used_cities)
                })

                self._pending_answer = None
                start_time = time.time()
                answered = False

                while time.time() - start_time < turn_time and self.running and not self.game_ended:
                    with self.lock:
                        if self._pending_answer is not None:
                            p_idx, city = self._pending_answer
                            self._pending_answer = None

                            if p_idx != self.current_player:
                                self.send_to(p_idx, {
                                    'type': 'error',
                                    'message': 'Сейчас не ваш ход!'
                                })
                                continue

                            ok, reason = self.validate_city(city, p_idx)
                            if ok:
                                original = self.find_original_name(normalize(city))
                                self.used_cities.add(normalize(city))
                                next_letter = get_required_letter(original)

                                available = self.check_available_cities(next_letter)
                                no_cities_on_letter = len(available) == 0

                                if no_cities_on_letter:
                                    new_letter = self.get_random_letter()
                                    
                                    if not new_letter:
                                        self.end_game('Все города использованы!', winner=-1)
                                        return

                                    self.required_letter = new_letter

                                    self.broadcast({
                                        'type': 'city_accepted',
                                        'city': original,
                                        'player': p_idx,
                                        'player_name': self.player_names[p_idx],
                                        'next_letter': self.required_letter,
                                        'no_cities_warning': True,
                                        'warning_message': f"На букву '{next_letter}' городов не осталось! Новая буква: '{self.required_letter}'",
                                        'scores': self.scores,
                                        'lives': self.lives
                                    })
                                else:
                                    self.required_letter = next_letter
                                    self.scores[p_idx] += len(original)

                                    self.broadcast({
                                        'type': 'city_accepted',
                                        'city': original,
                                        'player': p_idx,
                                        'player_name': self.player_names[p_idx],
                                        'next_letter': next_letter,
                                        'no_cities_warning': False,
                                        'scores': self.scores,
                                        'lives': self.lives
                                    })

                                self.current_player = 1 - self.current_player
                                answered = True
                                break
                            else:
                                self.send_to(p_idx, {
                                    'type': 'city_rejected',
                                    'city': city,
                                    'reason': reason
                                })

                    elapsed = time.time() - start_time
                    remaining = max(0, turn_time - elapsed)
                    self.broadcast({
                        'type': 'timer_tick',
                        'remaining': remaining,
                        'total': turn_time
                    })
                    time.sleep(0.3)

                if not answered and self.running and not self.game_ended:
                    # ТАЙМАУТ
                    loser = self.current_player
                    self.lives[loser] -= 1
                    
                    new_letter = self.get_random_letter()
                    
                    if new_letter:
                        self.required_letter = new_letter
                        timeout_msg = f"Время вышло! {self.player_names[loser]} теряет жизнь! (осталось: {self.lives[loser]}) Новая буква: '{new_letter}'"
                    else:
                        timeout_msg = f"Время вышло! {self.player_names[loser]} теряет жизнь! (осталось: {self.lives[loser]})"

                    print(f"[СЕРВЕР] {timeout_msg}")

                    self.broadcast({
                        'type': 'timeout',
                        'player': loser,
                        'player_name': self.player_names[loser],
                        'lives': self.lives,
                        'scores': self.scores,
                        'new_letter': new_letter,
                        'message': timeout_msg
                    })

                    self.current_player = 1 - self.current_player
                    time.sleep(3)

                if answered:
                    time.sleep(1.5)
                    
        except Exception as e:
            print(f"[СЕРВЕР] Ошибка в game_loop: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5555
    server = GameServer(port=port)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[СЕРВЕР] Остановлен пользователем.")
    except Exception as e:
        print(f"\n[СЕРВЕР] Критическая ошибка: {e}")
        traceback.print_exc()