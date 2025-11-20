"""
Encoding utilities for GameSpy protocol

Based on dwc_network_server_emulator
"""


def base32_encode(num: int, reverse: bool = True) -> str:
    """
    Encode a number in base 32.

    Uses custom alphabet: 0123456789abcdefghijklmnopqrstuv
    Result string is reversed by default (for GameSpy uniquenick generation).

    Args:
        num: Integer to encode
        reverse: Whether to reverse the result (default: True)

    Returns:
        Base32 encoded string

    Example:
        >>> base32_encode(12345)
        'ni60'
    """
    alpha = "0123456789abcdefghijklmnopqrstuv"

    encoded = ""
    while num > 0:
        encoded += alpha[num & 0x1f]
        num >>= 5

    # Pad to at least 1 character
    if not encoded:
        encoded = "0"

    if reverse:
        encoded = encoded[::-1]

    return encoded


def base32_decode(s: str, reverse: bool = False) -> int:
    """
    Decode a base32 encoded string to integer.

    Uses custom alphabet: 0123456789abcdefghijklmnopqrstuv
    Input string is not reversed by default.

    Args:
        s: Base32 encoded string
        reverse: Whether to reverse input first (default: False)

    Returns:
        Decoded integer

    Example:
        >>> base32_decode('ni60')
        12345
    """
    alpha = "0123456789abcdefghijklmnopqrstuv"

    if reverse:
        s = s[::-1]

    result = 0
    for char in s:
        result = (result << 5) | alpha.index(char)

    return result
