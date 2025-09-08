IO_BASE  = "https://io.brager.pl"         # API + login + WS
ONE_BASE = "https://one.brager.pl"        # assety frontendu
API_BASE = f"{IO_BASE}/v1"

# HTTP dekoracja (dla assetów/frontu)
ORIGIN  = ONE_BASE
REFERER = f"{ONE_BASE}/"

# WS / Socket.IO
WS_NAMESPACE = "/ws"
SOCK_PATH    = "/socket.io"

# Endpoints
AUTH_URL = f"{API_BASE}/auth/user"
