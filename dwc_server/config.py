"""
Configuration for DWC GameSpy Server
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Server configuration"""
    
    # NAS (Nintendo Authentication Server)
    NAS_HOST = os.getenv('NAS_HOST', '0.0.0.0')
    NAS_PORT = int(os.getenv('NAS_PORT', '80'))
    
    # GP (GameSpy Presence)
    GP_HOST = os.getenv('GP_HOST', '0.0.0.0')
    GP_PORT = int(os.getenv('GP_PORT', '29900'))
    
    # QR (Query & Reporting)
    QR_HOST = os.getenv('QR_HOST', '0.0.0.0')
    QR_PORT = int(os.getenv('QR_PORT', '27900'))
    
    # SB (Server Browser)
    SB_HOST = os.getenv('SB_HOST', '0.0.0.0')
    SB_PORT = int(os.getenv('SB_PORT', '28910'))
    
    # NN (NAT Negotiation)
    NN_HOST = os.getenv('NN_HOST', '0.0.0.0')
    NN_PORT = int(os.getenv('NN_PORT', '27901'))

    # DLS1 Server (Download/DLC Server)
    DLS1_HOST: str = os.getenv('DLS1_HOST', '0.0.0.0')
    DLS1_PORT: int = int(os.getenv('DLS1_PORT', '9003'))
    
    # Database URL (for API integration)
    DATABASE_URL = os.getenv('DATABASE_URL', 'http://admin:7999/api')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Security
    GAMESPY_SECRET = os.getenv('GAMESPY_SECRET', 'Ni8dan3hebd')  # Default from original DWC
    
    @classmethod
    def from_env(cls):
        """Create config from environment"""
        return cls()
    
    def __repr__(self):
        return f"<Config NAS={self.NAS_HOST}:{self.NAS_PORT} GP={self.GP_HOST}:{self.GP_PORT}>"


# Singleton instance
config = Config()