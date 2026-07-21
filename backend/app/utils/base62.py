ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = 62


def encode(num: int) -> str:
    """Encodes a given integer to a base62 string."""
    if num == 0:
        return ALPHABET[0]
    chars = []
    while num > 0:
        num, rem = divmod(num, BASE)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))

def decode(short_code: str) -> int:
    """Decodes a base62 string back to the original integer."""
    num = 0
    for char in short_code:
        num = num * BASE + ALPHABET.index(char)
    return num