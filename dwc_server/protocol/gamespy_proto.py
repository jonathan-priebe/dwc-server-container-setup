"""
GameSpy Protocol utilities

Handles parsing and building GameSpy messages
"""

import logging

logger = logging.getLogger(__name__)


def parse_gamespy_message(data: bytes) -> dict:
    """
    Parse GameSpy message format
    
    GameSpy uses key-value pairs separated by backslashes:
    \\key\\value\\key2\\value2\\final\\
    
    Args:
        data: Raw bytes from GameSpy client
        
    Returns:
        Dictionary of key-value pairs
        
    Example:
        >>> parse_gamespy_message(b'\\\\login\\\\\\\\challenge\\\\12345\\\\final\\\\')
        {'login': '', 'challenge': '12345', 'final': ''}
    """
    try:
        # Decode with latin-1 (GameSpy uses extended ASCII)
        msg = data.decode('latin-1', errors='ignore')
        
        # Split by backslash
        parts = msg.split('\\')
        
        # Remove empty first element if present
        if parts and parts[0] == '':
            parts = parts[1:]
        
        # Build dictionary from key-value pairs
        result = {}
        for i in range(0, len(parts) - 1, 2):
            key = parts[i]
            value = parts[i + 1] if i + 1 < len(parts) else ''
            result[key] = value
        
        return result
    
    except Exception as e:
        logger.error(f"Error parsing GameSpy message: {e}")
        return {}


def build_gamespy_message(params: dict) -> bytes:
    """
    Build GameSpy message format
    
    Args:
        params: Dictionary of key-value pairs
        
    Returns:
        Encoded GameSpy message
        
    Example:
        >>> build_gamespy_message({'lc': '2', 'sesskey': '12345'})
        b'\\\\lc\\\\2\\\\sesskey\\\\12345\\\\final\\\\'
    """
    msg = ''
    for key, value in params.items():
        msg += f'\\{key}\\{value}'
    msg += '\\final\\'
    
    return msg.encode('latin-1')


def validate_gamespy_message(data: bytes) -> bool:
    """
    Validate that data is a proper GameSpy message
    
    Args:
        data: Raw bytes to validate
        
    Returns:
        True if valid GameSpy message
    """
    try:
        msg = data.decode('latin-1', errors='ignore')
        # GameSpy messages start and end with backslash
        return msg.startswith('\\') and '\\' in msg
    except:
        return False


class GameSpyProtocol:
    """GameSpy protocol handler"""
    
    @staticmethod
    def parse(data: bytes) -> dict:
        """Parse GameSpy message"""
        return parse_gamespy_message(data)
    
    @staticmethod
    def build(params: dict) -> bytes:
        """Build GameSpy message"""
        return build_gamespy_message(params)
    
    @staticmethod
    def validate(data: bytes) -> bool:
        """Validate GameSpy message"""
        return validate_gamespy_message(data)


if __name__ == '__main__':
    # Test the protocol
    print("GameSpy Protocol Test")
    print("=" * 60)
    
    # Test parsing
    test_messages = [
        b'\\login\\\\challenge\\12345\\user\\testuser\\final\\',
        b'\\\\lc\\\\2\\\\sesskey\\\\abcdef\\\\final\\\\',
        b'\\getprofile\\\\profileid\\\\1\\\\final\\\\',
    ]
    
    for msg in test_messages:
        print(f"\nOriginal: {msg}")
        parsed = parse_gamespy_message(msg)
        print(f"Parsed: {parsed}")
    
    # Test building
    print("\n" + "=" * 60)
    print("Building messages:")
    
    test_params = [
        {'lc': '2', 'sesskey': '12345', 'proof': 'abcdef'},
        {'getprofile': '', 'profileid': '1'},
    ]
    
    for params in test_params:
        built = build_gamespy_message(params)
        print(f"\nParams: {params}")
        print(f"Built: {built}")
        print(f"Re-parsed: {parse_gamespy_message(built)}")