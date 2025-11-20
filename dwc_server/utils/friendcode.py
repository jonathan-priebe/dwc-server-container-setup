"""
Friend Code generation utilities for Nintendo DS/Wii

Based on reverse-engineered algorithm from Tetris DS @ 02057A14
"""

import struct
import hashlib


def calculate_crc8(data: bytes) -> int:
    """
    Calculate CRC8 checksum for friend code generation
    
    Uses polynomial 0x07 (x^8 + x^2 + x + 1)
    
    Args:
        data: Bytes to calculate CRC for
        
    Returns:
        CRC8 checksum (0-255)
    """
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


def generate_friend_code(profile_id: int, game_code: str) -> int:
    """
    Generate Nintendo DS/Wii Friend Code from profile ID and game code

    Algorithm (verified from CaitSith2's reverse-engineered code):
    1. Create 8-byte buffer
    2. Bytes 0-3: profile_id as little-endian 32-bit integer
    3. Bytes 4-7: game_code as big-endian hex, then split little-endian
       (e.g., "ADAJ" -> 0x4144414A -> bytes [0x4A, 0x41, 0x44, 0x41] = "JADA")
    4. Calculate CRC8 of the 8-byte buffer
    5. Friend code = (crc & 0x7f) << 32 | profile_id

    Args:
        profile_id: Unique profile identifier (1-4294967295)
        game_code: Game identifier - must be at least 4 characters
                   Only the first 4 characters are used for CRC calculation

    Returns:
        Friend code as 64-bit integer

    Example:
        >>> generate_friend_code(88, 'ADAJ')
        369367187544
        >>> format_friend_code(369367187544)
        '3693-6718-7544'
    """
    # Ensure profile_id is within valid range
    if not (1 <= profile_id <= 0xFFFFFFFF):
        raise ValueError(f"profile_id must be between 1 and {0xFFFFFFFF}")

    # game_code must be at least 4 characters
    if len(game_code) < 4:
        raise ValueError("game_code must be at least 4 characters")

    # Build the 8-byte CRC buffer
    # Bytes 0-3: profile_id little-endian
    # Bytes 4-7: game_code (first 4 chars) as "magic" little-endian

    # Convert game_id to "magic" number (big-endian interpretation)
    # e.g., "ADAJ" -> 0x4144414A
    game_id_4 = game_code[:4]
    magic = int.from_bytes(game_id_4.encode('ascii'), byteorder='big')

    # Build buffer with both values as little-endian
    buffer = struct.pack('<II', profile_id, magic)

    # Calculate CRC8
    crc = calculate_crc8(buffer)

    # Build friend code: (crc & 0x7f) in upper 32 bits, profile_id in lower 32 bits
    friend_code = ((crc & 0x7F) << 32) | profile_id

    return friend_code


def format_friend_code(friend_code: int) -> str:
    """
    Format friend code as XXXX-XXXX-XXXX

    The friend code integer is formatted as a 12-digit decimal number,
    then split into three groups of 4 digits.

    Args:
        friend_code: Friend code as integer

    Returns:
        Formatted friend code string

    Example:
        >>> format_friend_code(55_00000087)  # CRC=55, profile_id=87
        '5500-0000-0087'
    """
    # Format as 12-digit decimal number with leading zeros
    fc_str = f"{friend_code:012d}"

    # Split into three 4-digit groups
    return f"{fc_str[0:4]}-{fc_str[4:8]}-{fc_str[8:12]}"


def parse_friend_code(formatted: str) -> int:
    """
    Parse formatted friend code back to integer

    The friend code string (XXXX-XXXX-XXXX) is treated as a 12-digit
    decimal number.

    Args:
        formatted: Friend code string in format XXXX-XXXX-XXXX

    Returns:
        Friend code as integer

    Raises:
        ValueError: If format is invalid

    Example:
        >>> parse_friend_code('5500-0000-0087')
        5500000087
    """
    # Remove any spaces and dashes
    formatted = formatted.strip().replace('-', '')

    # Should be 12 digits
    if len(formatted) != 12:
        raise ValueError(f"Invalid friend code format: must be 12 digits (XXXX-XXXX-XXXX)")

    try:
        friend_code = int(formatted)
    except ValueError:
        raise ValueError(f"Invalid friend code format: must be numeric")

    return friend_code


def get_profile_id_from_friend_code(friend_code: int) -> int:
    """
    Extract profile ID from friend code

    Args:
        friend_code: Friend code as integer

    Returns:
        Profile ID (lower 32 bits)

    Example:
        >>> get_profile_id_from_friend_code(369367187544)
        88
    """
    return friend_code & 0xFFFFFFFF


def verify_friend_code(friend_code: int, game_id: str) -> bool:
    """
    Verify that a friend code is valid for a given game

    Args:
        friend_code: Friend code to verify
        game_id: Game ID to verify against

    Returns:
        True if valid, False otherwise

    Example:
        >>> verify_friend_code(369367187544, 'ADAJ')
        True
        >>> verify_friend_code(369367187544, 'WRONG')
        False
    """
    profile_id = get_profile_id_from_friend_code(friend_code)
    expected_fc = generate_friend_code(profile_id, game_id)
    return friend_code == expected_fc


# Convenience function for Django models
def calculate_friend_code_for_profile(profile_id: int, game_id: str) -> str:
    """
    Calculate and format friend code for a profile

    This is a convenience function that combines generate_friend_code
    and format_friend_code for easy use in Django models.

    Args:
        profile_id: Profile ID
        game_id: Game ID

    Returns:
        Formatted friend code string

    Example:
        >>> calculate_friend_code_for_profile(88, 'ADAJ')
        '3693-6718-7544'
    """
    fc = generate_friend_code(profile_id, game_id)
    return format_friend_code(fc)


if __name__ == '__main__':
    # Test the functions
    print("Friend Code Generation Test")
    print("=" * 50)
    
    test_cases = [
        (1, 'ADAJ'),
        (2, 'ADAJ'),
        (3, 'ADAJ'),
        (1000, 'RMCJ'),
        (9999999, 'CPUE'),
    ]
    
    for profile_id, game_id in test_cases:
        fc = generate_friend_code(profile_id, game_id)
        formatted = format_friend_code(fc)
        parsed = parse_friend_code(formatted)
        extracted_id = get_profile_id_from_friend_code(fc)
        is_valid = verify_friend_code(fc, game_id)
        
        print(f"\nProfile ID: {profile_id}, Game: {game_id}")
        print(f"  Friend Code (int): {fc}")
        print(f"  Friend Code (formatted): {formatted}")
        print(f"  Parsed back: {parsed}")
        print(f"  Extracted Profile ID: {extracted_id}")
        print(f"  Valid: {is_valid}")
        print(f"  Match: {'✓' if fc == parsed and extracted_id == profile_id else '✗'}")