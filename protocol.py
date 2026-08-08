"""
Простой JSON-based протокол поверх TCP.
Каждое сообщение: 4 байта длины (big-endian) + JSON payload.
"""
import json
import struct
import asyncio
from typing import Any


def encode_message(data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
    return struct.pack('!I', len(payload)) + payload


async def read_message(reader: asyncio.StreamReader) -> dict | None:
    header = await reader.readexactly(4)
    length = struct.unpack('!I', header)[0]
    if length > 1_000_000:
        return None
    payload = await reader.readexactly(length)
    return json.loads(payload.decode('utf-8'))


def send_message_sync(sock, data: dict):
    """Синхронная отправка для использования в потоке."""
    msg = encode_message(data)
    sock.sendall(msg)


def recv_message_sync(sock) -> dict | None:
    """Синхронная приёмка для использования в потоке."""
    header = b''
    while len(header) < 4:
        chunk = sock.recv(4 - len(header))
        if not chunk:
            return None
        header += chunk
    length = struct.unpack('!I', header)[0]
    if length > 1_000_000:
        return None
    payload = b''
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            return None
        payload += chunk
    return json.loads(payload.decode('utf-8'))