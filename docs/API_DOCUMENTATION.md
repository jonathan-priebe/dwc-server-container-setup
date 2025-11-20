# 🌐 DWC Server REST API Documentation

## Base URL
```
http://localhost:8001/api/
```

## Authentication
All endpoints require authentication. Use Django session authentication or token authentication.

## Endpoints

### 📊 Statistics

#### Get Overview Stats
```http
GET /api/stats/
```

**Response:**
```json
{
  "total_consoles": 4,
  "total_profiles": 5,
  "total_bans": 2,
  "online_consoles": 0,
  "online_servers": 3,
  "recent_logins": 15,
  "logins_today": 25,
  "consoles_by_platform": [
    {"platform": "DS", "count": 2},
    {"platform": "Wii", "count": 1},
    {"platform": "DSi", "count": 1}
  ],
  "top_games": [
    {"game_id": "ADAJ", "count": 2},
    {"game_id": "IRAJ", "count": 1}
  ]
}
```

---

### 📱 Consoles

#### List All Consoles
```http
GET /api/consoles/
```

**Query Parameters:**
- `platform` - Filter by platform (DS, DSi, Wii)
- `enabled` - Filter by enabled status (true/false)
- `search` - Search in MAC, user_id, device_name
- `ordering` - Sort by field (e.g., `-last_seen`)

**Response:**
```json
[
  {
    "mac_address": "00:09:bf:11:22:33",
    "user_id": "6818938419496",
    "device_name": "melonDS",
    "platform": "DS",
    "enabled": true,
    "registered_at": "2025-11-05T14:20:00Z",
    "last_seen": "2025-11-05T14:45:00Z",
    "status": "online",
    "profile_count": 1
  }
]
```

#### Get Online Consoles
```http
GET /api/consoles/online/
```

Returns consoles active in the last 5 minutes.

#### Get Specific Console
```http
GET /api/consoles/{mac_address}/
```

#### Create Console
```http
POST /api/consoles/
Content-Type: application/json

{
  "mac_address": "00:11:22:33:44:55",
  "user_id": "1234567890123",
  "device_name": "My DS",
  "platform": "DS",
  "enabled": true
}
```

#### Enable/Disable Console
```http
POST /api/consoles/{mac_address}/enable/
POST /api/consoles/{mac_address}/disable/
```

---

### 👥 Profiles

#### List All Profiles
```http
GET /api/profiles/
```

**Query Parameters:**
- `game_id` - Filter by game
- `enabled` - Filter by status
- `user_id` - Filter by user
- `search` - Search in profile_id, user_id, uniquenick

**Response:**
```json
[
  {
    "profile_id": 1,
    "user_id": "6818938419496",
    "game_id": "ADAJ",
    "friend_code": "0012-0000-0001",
    "enabled": true,
    "created_at": "2025-11-05T14:20:00Z"
  }
]
```

#### Get Profile Details
```http
GET /api/profiles/{id}/
```

**Response:**
```json
{
  "profile_id": 1,
  "user_id": "6818938419496",
  "game_id": "ADAJ",
  "console": 1,
  "console_info": {
    "mac_address": "00:09:bf:11:22:33",
    "device_name": "melonDS",
    "platform": "DS"
  },
  "friend_code": "0012-0000-0001",
  "enabled": true,
  "created_at": "2025-11-05T14:20:00Z",
  "gs_broadcast_code": "ADAJ12xxx3",
  "uniquenick": "melonDS_ADAJ"
}
```

#### Get Profiles by Game
```http
GET /api/profiles/by_game/?game_id=ADAJ
```

#### Lookup by Friend Code
```http
GET /api/profiles/lookup_friend_code/?friend_code=0012-0000-0001
```

#### Create Profile
```http
POST /api/profiles/
Content-Type: application/json

{
  "user_id": "1234567890123",
  "game_id": "ADAJ",
  "console": 1,
  "enabled": true
}
```

---

### 🎮 Game Servers

#### List All Servers
```http
GET /api/game-servers/
```

**Query Parameters:**
- `game_name` - Filter by game

**Response:**
```json
[
  {
    "id": 1,
    "server_id": "pokemondpds_1_1234",
    "game_name": "pokemondpds",
    "host_profile": 1,
    "host_profile_info": {
      "profile_id": 1,
      "friend_code": "0012-0000-0001",
      "console_name": "melonDS"
    },
    "address": "192.168.1.10:27000",
    "ip_address": "192.168.1.10",
    "port": 27000,
    "max_players": 4,
    "current_players": 2,
    "game_data": {
      "mapname": "test_map",
      "gamemode": "standard"
    },
    "registered_at": "2025-11-05T14:20:00Z",
    "last_heartbeat": "2025-11-05T14:45:00Z",
    "is_online": true
  }
]
```

#### Get Online Servers
```http
GET /api/game-servers/online/
```

Returns servers with heartbeat in last 2 minutes.

#### Get Servers by Game
```http
GET /api/game-servers/by_game/?game_name=pokemondpds
```

#### Update Server Heartbeat
```http
POST /api/game-servers/{id}/heartbeat/
Content-Type: application/json

{
  "current_players": 3
}
```

---

### 🔐 NAS Logins

#### List All Logins
```http
GET /api/nas-logins/
```

**Query Parameters:**
- `user_id` - Filter by user
- `ip_address` - Filter by IP

**Response:**
```json
[
  {
    "id": 1,
    "user_id": "6818938419496",
    "auth_token": "token_123456",
    "data": {
      "macadr": "00:09:bf:11:22:33",
      "devname": "melonDS",
      "action": "login",
      "lang": "01"
    },
    "timestamp": "2025-11-05T14:45:00Z",
    "ip_address": "192.168.1.100"
  }
]
```

#### Get Recent Logins (Last Hour)
```http
GET /api/nas-logins/recent/
```

---

### ⛔ Bans

#### List All Bans
```http
GET /api/bans/
```

**Query Parameters:**
- `ban_type` - Filter by type (ip, mac, profile, userid)

**Response:**
```json
[
  {
    "id": 1,
    "ban_type": "ip",
    "ban_type_display": "IP Address",
    "identifier": "192.168.1.666",
    "reason": "Suspicious activity",
    "banned_at": "2025-11-05T14:00:00Z",
    "expires_at": null,
    "banned_by": "admin",
    "is_active": true
  }
]
```

#### Get Active Bans
```http
GET /api/bans/active/
```

#### Check if Banned
```http
POST /api/bans/check/
Content-Type: application/json

{
  "ban_type": "mac",
  "identifier": "00:de:ad:be:ef:00"
}
```

**Response:**
```json
{
  "banned": true,
  "reason": "Hacking attempt",
  "expires_at": "2025-11-12T14:00:00Z"
}
```

#### Create Ban
```http
POST /api/bans/
Content-Type: application/json

{
  "ban_type": "mac",
  "identifier": "00:11:22:33:44:55",
  "reason": "Cheating",
  "expires_at": "2025-12-01T00:00:00Z",
  "banned_by": "admin"
}
```

---

### 📈 Server Statistics

#### List All Statistics
```http
GET /api/statistics/
```

#### Get Latest Stats
```http
GET /api/statistics/latest/
```

#### Get Stats History
```http
GET /api/statistics/history/?days=7
```

**Response:**
```json
[
  {
    "id": 1,
    "timestamp": "2025-11-05T00:00:00Z",
    "active_consoles": 120,
    "active_profiles": 180,
    "active_servers": 25,
    "total_logins_today": 450
  }
]
```

---

## Response Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `204 No Content` - Success, no content to return
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

---

## Examples

### Python Example
```python
import requests

# Get stats
response = requests.get('http://localhost:8001/api/stats/')
stats = response.json()
print(f"Total Consoles: {stats['total_consoles']}")

# Get online consoles
response = requests.get('http://localhost:8001/api/consoles/online/')
consoles = response.json()
for console in consoles:
    print(f"{console['device_name']}: {console['status']}")

# Lookup friend code
response = requests.get(
    'http://localhost:8001/api/profiles/lookup_friend_code/',
    params={'friend_code': '0012-0000-0001'}
)
profile = response.json()
print(f"Profile ID: {profile['profile_id']}")
```

### JavaScript Example
```javascript
// Get stats
fetch('http://localhost:8001/api/stats/')
  .then(response => response.json())
  .then(stats => {
    console.log(`Total Consoles: ${stats.total_consoles}`);
  });

// Create new ban
fetch('http://localhost:8001/api/bans/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    ban_type: 'ip',
    identifier: '192.168.1.999',
    reason: 'Testing',
    banned_by: 'admin'
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

### cURL Examples
```bash
# Get stats
curl http://localhost:8001/api/stats/

# Search consoles
curl "http://localhost:8001/api/consoles/?search=melon"

# Filter profiles by game
curl "http://localhost:8001/api/profiles/?game_id=ADAJ"

# Create new console
curl -X POST http://localhost:8001/api/consoles/ \
  -H "Content-Type: application/json" \
  -d '{
    "mac_address": "00:99:88:77:66:55",
    "user_id": "9999999999999",
    "device_name": "Test Console",
    "platform": "DS"
  }'
```

---

## Notes

- All datetime fields are in ISO 8601 format (UTC)
- MAC addresses use colon-separated format: `00:09:bf:11:22:33`
- Friend codes are formatted as: `XXXX-XXXX-XXXX`
- The API uses pagination for list endpoints (default 50 items per page)

---

## Testing with Browsable API

Django REST Framework provides a browsable API interface. Simply visit any endpoint in your browser while logged in to test the API interactively:

http://localhost:8001/api/

This provides forms for testing POST/PUT/DELETE requests and viewing responses.
