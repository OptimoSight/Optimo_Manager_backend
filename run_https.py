import uvicorn
import os
import socket

CERT_FILE = './localhost+1.pem'
KEY_FILE = './localhost+1-key.pem'

if not (os.path.isfile(CERT_FILE) and os.path.isfile(KEY_FILE)):
    raise FileNotFoundError(
        f"Cannot find certificate files.\nExpected:\n  {CERT_FILE}\n  {KEY_FILE}"
    )

# Detect LAN IP
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP

lan_ip = get_lan_ip()
port = 42413

if __name__ == "__main__":
    print(f"✅ Starting FastAPI HTTPS server...")
    print(f" - Localhost URL: https://localhost:{port}")
    print(f" - LAN URL      : https://{lan_ip}:{port}")
    print(f" - Using app    : app.py (unified application)\n")
    
    uvicorn.run(
        "main:app",          # unified app
        host="0.0.0.0",
        port=port,
        reload=True,
        ssl_certfile=CERT_FILE,
        ssl_keyfile=KEY_FILE
    )