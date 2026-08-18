"""Google Translate web-compatible ``tk`` token generation.

The implementation mirrors the small JavaScript arithmetic routine used by
the web-compatible request format. It is deliberately isolated from HTTP so
that request changes do not affect the arithmetic and vice versa.
"""

from __future__ import annotations

_B = 406644
_B1 = 3293161072
_LEFT_PATTERN = "+-a^+6"
_RIGHT_PATTERN = "+-3^+b+-f"
_TOKEN_MODULUS = 1_000_000
_UINT32_MASK = 0xFFFFFFFF
_INT32_SIGN = 0x80000000


def _to_uint32(value: int) -> int:
    """Apply JavaScript's unsigned 32-bit conversion."""

    return int(value) & _UINT32_MASK


def _to_int32(value: int) -> int:
    """Apply JavaScript's signed 32-bit conversion."""

    unsigned = _to_uint32(value)
    if unsigned & _INT32_SIGN:
        return unsigned - (_UINT32_MASK + 1)
    return unsigned


def _js_xor(left: int, right: int) -> int:
    """Return JavaScript-style signed 32-bit XOR."""

    return _to_int32(_to_int32(left) ^ _to_int32(right))


def _js_left_shift(value: int, shift: int) -> int:
    """Return JavaScript-style signed 32-bit left shift."""

    return _to_int32(_to_int32(value) << (shift & 31))


def _js_unsigned_right_shift(value: int, shift: int) -> int:
    """Return JavaScript's ``>>>`` result rather than Python's ``>>``."""

    return _to_uint32(value) >> (shift & 31)


def _right_left(value: int, pattern: str) -> int:
    """Port the JavaScript ``RL`` routine with explicit 32-bit semantics."""

    result = value
    for index in range(0, len(pattern) - 2, 3):
        shift_character = pattern[index + 2]
        shift = (
            ord(shift_character) - 87
            if "a" <= shift_character
            else int(shift_character)
        )

        if pattern[index + 1] == "+":
            shifted = _js_unsigned_right_shift(result, shift)
        else:
            shifted = _js_left_shift(result, shift)

        if pattern[index] == "+":
            # JavaScript addition is numeric addition, not a 32-bit
            # conversion. A later XOR/shift performs the next conversion.
            result = result + shifted
        else:
            result = _js_xor(result, shifted)
    return result


def _utf16_code_units(text: str) -> list[int]:
    """Return JavaScript-like UTF-16 code units, including lone surrogates."""

    encoded = text.encode("utf-16-le", "surrogatepass")
    return [
        encoded[index] | (encoded[index + 1] << 8)
        for index in range(0, len(encoded), 2)
    ]


def _utf8_bytes_from_javascript_string(text: str) -> list[int]:
    """Reproduce the web routine's UTF-8 conversion over UTF-16 units."""

    units = _utf16_code_units(text)
    result: list[int] = []
    index = 0
    while index < len(units):
        code_point = units[index]
        if (
            0xD800 <= code_point <= 0xDBFF
            and index + 1 < len(units)
            and 0xDC00 <= units[index + 1] <= 0xDFFF
        ):
            code_point = (
                0x10000
                + ((code_point - 0xD800) << 10)
                + (units[index + 1] - 0xDC00)
            )
            index += 1

        if code_point < 0x80:
            result.append(code_point)
        elif code_point < 0x800:
            result.extend(
                (
                    (code_point >> 6) | 0xC0,
                    (code_point & 0x3F) | 0x80,
                )
            )
        elif code_point < 0x10000:
            result.extend(
                (
                    (code_point >> 12) | 0xE0,
                    ((code_point >> 6) & 0x3F) | 0x80,
                    (code_point & 0x3F) | 0x80,
                )
            )
        else:
            result.extend(
                (
                    (code_point >> 18) | 0xF0,
                    ((code_point >> 12) & 0x3F) | 0x80,
                    ((code_point >> 6) & 0x3F) | 0x80,
                    (code_point & 0x3F) | 0x80,
                )
            )
        index += 1
    return result


def generate_token(text: str) -> str:
    """Generate a deterministic ``tk`` token for one translation string."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    value = _B
    for byte in _utf8_bytes_from_javascript_string(text):
        value += byte
        value = _right_left(value, _LEFT_PATTERN)
    value = _right_left(value, _RIGHT_PATTERN)
    value = _js_xor(value, _B1)
    if value < 0:
        # The JavaScript implementation converts a negative signed result to
        # its unsigned 32-bit representation before applying the modulus.
        value = _to_uint32(value)
    value %= _TOKEN_MODULUS

    suffix = _to_uint32(_js_xor(value, _B))
    return f"{value}.{suffix}"


__all__ = ["generate_token"]
