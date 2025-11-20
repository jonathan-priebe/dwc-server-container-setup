# 🎮 DS/Wii GameSpy Server - Funktionierende Ressourcen

## ⚠️ Wichtig: NintendoClients ist NICHT für DS!

**NintendoClients** = Wii U, 3DS, Switch (NEX Protokoll)
**GameSpy** = DS, Wii (altes WFC Protokoll)

Das sind **komplett verschiedene** Protokolle!

## ✅ Funktionierende Ressourcen für DS/Wii (GameSpy)

### 1. **DWC Network Server Emulator** (Deine Basis)
```
https://github.com/barronwaffles/dwc_network_server_emulator
```
- Python 2 + Twisted
- Vollständig funktionierende Referenz
- **Nutze als Protokoll-Referenz!**

### 2. **OpenSpy Core v2**
```
https://github.com/openspy/openspy-core-v2
```
- C++ Implementation
- Sehr vollständig
- **Beste Protokoll-Dokumentation!**

### 3. **Luigi Auriemma's Tools**
```
http://aluigi.altervista.org/
```
- `enctypex_decoder` - GameSpy Encryption
- `gslist` - GameSpy Server Browser
- Alte aber funktionierende Tools

### 4. **Wiimmfi Dokumentation**
```
https://wiimmfi.de/
```
- Error Codes: https://wiimmfi.de/error
- Sehr gute Fehler-Dokumentation

## 📚 Twisted vs. Asyncio - Praktischer Vergleich

### ❌ **Twisted** (Alt, kompliziert)

```python
from twisted.internet import reactor, protocol
from twisted.protocols import basic

class GameSpyProtocol(basic.LineReceiver):
    def connectionMade(self):
        print("Client connected")
    
    def lineReceived(self, line):
        # Parse GameSpy command
        if line.startswith(b'\\login\\'):
            self.handle_login(line)
    
    def handle_login(self, data):
        # Complex parsing
        pass

class GameSpyFactory(protocol.ServerFactory):
    protocol = GameSpyProtocol

reactor.listenTCP(29900, GameSpyFactory())
reactor.run()
```

**Probleme:**
- `reactor.run()` blockiert alles
- Komplizierte `Factory`/`Protocol` Patterns
- Schwer zu testen
- Große Dependency

### ✅ **Asyncio** (Modern, einfach)

```python
import asyncio

class GameSpyServer:
    async def handle_client(self, reader, writer):
        print("Client connected")
        
        while True:
            data = await reader.readline()
            if not data:
                break
            
            # Parse GameSpy command
            if data.startswith(b'\\login\\'):
                await self.handle_login(data, writer)
        
        writer.close()
        await writer.wait_closed()
    
    async def handle_login(self, data, writer):
        # Simple parsing
        response = b'\\lc\\2\\sesskey\\...'
        writer.write(response)
        await writer.drain()
    
    async def start(self):
        server = await asyncio.start_server(
            self.handle_client, 
            '0.0.0.0', 
            29900
        )
        async with server:
            await server.serve_forever()

# Run
asyncio.run(GameSpyServer().start())
```

**Vorteile:**
- Native Python (keine extra Dependency!)
- Einfacher zu verstehen
- Einfacher zu testen
- Besser maintained

## 🔧 GameSpy Protokoll Basics

### Protokoll-Format

GameSpy nutzt **Key-Value Pairs** mit `\` als Delimiter:

```
\login\\challenge\XXXXXXXX\user\username\final\
```

Parsing:
```python
def parse_gamespy_message(data: bytes) -> dict:
    """Parse GameSpy message format"""
    msg = data.decode('latin-1')
    parts = msg.split('\\')
    
    # Remove empty first element
    if parts[0] == '':
        parts = parts[1:]
    
    # Create dict from key-value pairs
    result = {}
    for i in range(0, len(parts)-1, 2):
        key = parts[i]
        value = parts[i+1] if i+1 < len(parts) else ''
        result[key] = value
    
    return result

# Example
msg = b'\\login\\\\challenge\\12345\\user\\testuser\\final\\'
parsed = parse_gamespy_message(msg)
# {'login': '', 'challenge': '12345', 'user': 'testuser', 'final': ''}
```

## 📖 GameSpy Server Typen

### 1. **NAS (Nintendo Authentication Server)**
- **Port:** 80 (HTTP)
- **Protokoll:** HTTP POST
- **Zweck:** Erste Authentifizierung, gibt GameSpy Server zurück

```python
# HTTP POST to /ac
# Form data: action=login, userid=XXX, ...
# Response: returncd=001\nloc=gamespy.com\n...
```

### 2. **GP (GameSpy Presence)**
- **Port:** 29900 (TCP)
- **Protokoll:** GameSpy Key-Value
- **Zweck:** Login, Profil, Status, Buddies

```python
# Client -> Server
\login\\challenge\XXXXXXXX\user\username\...

# Server -> Client
\lc\2\sesskey\XXXXXXXX\proof\YYYYYYYY\...
```

### 3. **QR (Query & Reporting)**
- **Port:** 27900 (UDP)
- **Protokoll:** GameSpy Binary + Key-Value
- **Zweck:** Server Registration, Heartbeats

```python
# Server sends heartbeat every 60 seconds
\heartbeat\27900\gamename\pokemondpds\...
```

### 4. **SB (Server Browser)**
- **Port:** 28910 (TCP)
- **Protokoll:** GameSpy Key-Value
- **Zweck:** Server List, Search

### 5. **NN (NAT Negotiation)**
- **Port:** 27901 (UDP)
- **Protokoll:** Binary
- **Zweck:** NAT Traversal für P2P

## 🧪 Testing ohne Hardware

### 1. **Wireshark Captures**
```bash
# Capture DWC traffic von echtem DS
tcpdump -i any -w ds_traffic.pcap port 29900 or port 27900

# Analysieren
wireshark ds_traffic.pcap
```

### 2. **Test mit Python Client**
```python
import socket

# Simuliere DS Login
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('localhost', 29900))

# Send login
login_msg = b'\\login\\\\challenge\\12345\\user\\test\\final\\'
sock.send(login_msg)

# Receive response
response = sock.recv(4096)
print(response)

sock.close()
```

### 3. **Unit Tests**
```python
import pytest
from your_server import GameSpyServer

@pytest.mark.asyncio
async def test_gamespy_login():
    server = GameSpyServer()
    
    # Simulate client message
    msg = b'\\login\\\\challenge\\12345\\user\\test\\final\\'
    
    response = await server.handle_login(msg)
    
    assert b'\\lc\\2\\' in response
    assert b'sesskey' in response
```

## 🎯 Dein Entwicklungsplan

### Phase 1: Verstehe das Protokoll (1 Woche)
1. ✅ Studiere DWC Emulator Code
2. ✅ Capture echten DS Traffic mit Wireshark
3. ✅ Dokumentiere Protokoll-Flow
4. ✅ Erstelle Protokoll-Parser

### Phase 2: NAS Server (1 Woche)
1. ✅ Implementiere HTTP Server (aiohttp)
2. ✅ Handle `/ac` endpoint
3. ✅ Parse form data
4. ✅ Return korrekte response
5. ✅ Test mit echtem DS

### Phase 3: GameSpy GP Server (2 Wochen)
1. ✅ Implementiere TCP Server (asyncio)
2. ✅ Handle `\login\` command
3. ✅ Challenge-Response Auth
4. ✅ Profile Creation
5. ✅ Friend Code Generation
6. ✅ Test mit echtem DS

### Phase 4: GameSpy QR Server (1 Woche)
1. ✅ Implementiere UDP Server
2. ✅ Handle heartbeats
3. ✅ Server registration
4. ✅ Test mit echtem DS

### Phase 5: Weitere Server (2-3 Wochen)
1. ✅ Server Browser
2. ✅ NAT Negotiation
3. ✅ Stats Server
4. ✅ Full integration tests

## 📦 Minimal Working Example - NUR asyncio

```python
#!/usr/bin/env python3
"""
Minimal GameSpy GP Server mit asyncio (KEINE Twisted!)
"""
import asyncio
import hashlib
import secrets

class GameSpyGPServer:
    def __init__(self):
        self.sessions = {}
    
    def parse_message(self, data: bytes) -> dict:
        """Parse GameSpy message"""
        msg = data.decode('latin-1', errors='ignore')
        parts = msg.split('\\')
        
        if parts[0] == '':
            parts = parts[1:]
        
        result = {}
        for i in range(0, len(parts)-1, 2):
            if i+1 < len(parts):
                result[parts[i]] = parts[i+1]
        
        return result
    
    def build_message(self, params: dict) -> bytes:
        """Build GameSpy message"""
        msg = ''
        for key, value in params.items():
            msg += f'\\{key}\\{value}'
        msg += '\\final\\'
        return msg.encode('latin-1')
    
    async def handle_client(self, reader, writer):
        """Handle GameSpy client connection"""
        addr = writer.get_extra_info('peername')
        print(f"[GP] Client connected: {addr}")
        
        try:
            while True:
                # Read until \final\
                data = await reader.readuntil(b'\\final\\')
                
                if not data:
                    break
                
                # Parse message
                msg = self.parse_message(data)
                print(f"[GP] Received: {msg}")
                
                # Handle commands
                if 'login' in msg:
                    response = await self.handle_login(msg)
                    writer.write(response)
                    await writer.drain()
                
                elif 'logout' in msg:
                    break
                
        except Exception as e:
            print(f"[GP] Error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[GP] Client disconnected: {addr}")
    
    async def handle_login(self, msg: dict) -> bytes:
        """Handle login command"""
        # Generate session key
        sesskey = secrets.token_hex(16)
        
        # Generate proof (simplified)
        proof = hashlib.md5(sesskey.encode()).hexdigest()
        
        # Build response
        response = self.build_message({
            'lc': '2',
            'sesskey': sesskey,
            'proof': proof,
            'userid': '1234567890',
            'profileid': '1',
            'uniquenick': msg.get('user', 'unknown')
        })
        
        return response
    
    async def start(self, host='0.0.0.0', port=29900):
        """Start GameSpy GP server"""
        server = await asyncio.start_server(
            self.handle_client,
            host,
            port
        )
        
        print(f"[GP] Server listening on {host}:{port}")
        
        async with server:
            await server.serve_forever()

if __name__ == '__main__':
    server = GameSpyGPServer()
    asyncio.run(server.start())
```

## 🧪 Test Script

```python
#!/usr/bin/env python3
"""
Test GameSpy Server
"""
import asyncio

async def test_gamespy_server():
    reader, writer = await asyncio.open_connection('localhost', 29900)
    
    # Send login
    login = b'\\login\\\\challenge\\12345\\user\\testuser\\final\\'
    writer.write(login)
    await writer.drain()
    
    # Read response
    response = await reader.readuntil(b'\\final\\')
    print(f"Response: {response}")
    
    writer.close()
    await writer.wait_closed()

if __name__ == '__main__':
    asyncio.run(test_gamespy_server())
```

## 🎯 Zusammenfassung

**Twisted:** ❌ Veraltet, kompliziert, große Dependency
**Asyncio:** ✅ Modern, einfach, Python Standard

**Für DS/Wii brauchst du:**
- GameSpy Protokoll (NICHT NEX!)
- asyncio (NICHT Twisted!)
- DWC Emulator als Referenz

**Start hier:**
1. Implementiere einfachen GP Server (oben)
2. Teste mit Python Test-Client
3. Dann teste mit echtem DS
4. Erweitere Schritt für Schritt

Good luck! 🚀
