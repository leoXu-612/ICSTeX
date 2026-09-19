"""Stable, sortable ULID-style IDs for Blocks, layouts, sources, instances.

IDs are immutable internal identities (per the task list): 48-bit millisecond
timestamp (10 Crockford base32 chars) + 80 bits of randomness (16 chars),
prefixed by domain (``blk_``, ``lyt_``, ``src_``, ``ins_``).
"""
from __future__ import annotations

import random
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, width: int) -> str:
    chars: list[str] = []
    for _ in range(width):
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_id(prefix: str) -> str:
    timestamp = int(time.time() * 1000)
    randomness = random.getrandbits(80)
    return f"{prefix}_{_encode(timestamp, 10)}{_encode(randomness, 16)}"


def new_block_id() -> str:
    return new_id("blk")


def new_layout_id() -> str:
    return new_id("lyt")


def new_source_id() -> str:
    return new_id("src")


def new_instance_id() -> str:
    return new_id("ins")
