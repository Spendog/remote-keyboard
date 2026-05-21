from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect
import pyautogui
import socket
import qrcode
import io
import base64
import secrets
import logging
import logging.handlers
import datetime
import json
import pyperclip
import os
import subprocess
from OpenSSL import crypto

# Configure logging with rotating file handler
file_handler = logging.handlers.RotatingFileHandler('server.log', maxBytes=1024*1024, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# Security Token
AUTH_TOKEN = secrets.token_urlsafe(16)
CONNECTED_DEVICES = []

# State
TRUSTED_DEVICES = {} # IP -> Nickname
PENDING_DEVICES = [] # List of dicts
LOG_CACHE = []
LOGGING_ENABLED = True
DEBUG_MODE = False
CONFIG_FILE = 'config.json'

# Reduce latency for pyautogui
pyautogui.PAUSE = 0

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

HOST_IP = get_ip()
# We will use port 54321 and HTTPS
HOST_URL = f"https://{HOST_IP}:54321"

# Callback for GUI updates
gui_callback = None

def set_gui_callback(callback):
    global gui_callback
    gui_callback = callback

def notify_gui():
    if gui_callback:
        # Pass a snapshot of state
        state = {
            'connected': CONNECTED_DEVICES,
            'pending': PENDING_DEVICES,
            'trusted': TRUSTED_DEVICES, # Now a dict
            'logs': LOG_CACHE[-50:], # Send last 50 logs
            'debug_mode': DEBUG_MODE
        }
        gui_callback(state)

def log_event(message):
    # Only print if it's an error or important, or if specifically debugging
    # print(f"LOG: {message}") # Commented out to reduce noise
    if LOGGING_ENABLED:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        LOG_CACHE.append(entry)
        if len(LOG_CACHE) > 1000:
            LOG_CACHE.pop(0)
        notify_gui()

def load_config():
    global TRUSTED_DEVICES, AUTH_TOKEN, DEBUG_MODE
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                # Handle migration from list to dict
                loaded_trusted = data.get('trusted_devices', {})
                if isinstance(loaded_trusted, list):
                    TRUSTED_DEVICES = {ip: f"Device {ip}" for ip in loaded_trusted}
                else:
                    TRUSTED_DEVICES = loaded_trusted
                
                AUTH_TOKEN = data.get('auth_token')
                
                # Load debug mode setting
                if data.get('debug_mode') is not None:
                    set_debug_mode(data.get('debug_mode'), notify=False)
                    
                print(f"Loaded {len(TRUSTED_DEVICES)} trusted devices.")
        except Exception as e:
            print(f"Error loading config: {e}")
    
    if not AUTH_TOKEN:
        AUTH_TOKEN = secrets.token_urlsafe(16)
        save_config()

def get_last_known_ip():
    """Read last_known_ip from config without touching other state."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_known_ip')
        except Exception:
            pass
    return None

def save_config():
    try:
        data = {
            'trusted_devices': TRUSTED_DEVICES,
            'auth_token': AUTH_TOKEN,
            'debug_mode': DEBUG_MODE,
            'last_known_ip': HOST_IP
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving config: {e}")

def set_debug_mode(enabled, notify=True):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    if enabled:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug Mode ENABLED")
        log_event("Debug Mode ENABLED (Check server.log for full details)")
    else:
        logger.setLevel(logging.INFO)
        logger.info("Debug Mode DISABLED")
        log_event("Debug Mode DISABLED")
    save_config()
    if notify:
        notify_gui()

def approve_device(ip):
    TRUSTED_DEVICES[ip] = f"Device {ip}" # Default nickname
    save_config()
    # Remove from pending if there
    global PENDING_DEVICES
    PENDING_DEVICES = [d for d in PENDING_DEVICES if d['ip'] != ip]
    log_event(f"Device approved: {ip}")
    notify_gui()

def remove_device(ip):
    if ip in TRUSTED_DEVICES:
        del TRUSTED_DEVICES[ip]
        save_config()
        log_event(f"Device removed: {ip}")
        notify_gui()

def rename_device(ip, new_name):
    if ip in TRUSTED_DEVICES:
        TRUSTED_DEVICES[ip] = new_name
        save_config()
        log_event(f"Device renamed: {ip} -> {new_name}")
        notify_gui()

def toggle_logging(enabled):
    global LOGGING_ENABLED
    LOGGING_ENABLED = enabled
    status = "enabled" if enabled else "disabled"
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    LOG_CACHE.append(f"[{timestamp}] Logging {status}")
    notify_gui()

def clear_cache():
    global LOG_CACHE
    LOG_CACHE = []
    notify_gui()

def is_trusted(request_obj):
    ip = request_obj.remote_addr
    # Localhost always trusted
    if ip == '127.0.0.1' or ip == HOST_IP:
        return True
    return ip in TRUSTED_DEVICES

@app.route('/')
def dashboard():
    # Generate QR Code for the remote URL
    remote_url = f"{HOST_URL}/remote?token={AUTH_TOKEN}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(remote_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    qr_b64 = base64.b64encode(img_byte_arr).decode('utf-8')
    qr_url = f"data:image/png;base64,{qr_b64}"
    
    return render_template('dashboard.html', qr_code_url=qr_url, host_url=HOST_URL)

@app.route('/remote')
def remote():
    token = request.args.get('token')
    # log_event(f"Token check: Received='{token}', Expected='{AUTH_TOKEN}'") # Reduced noise
    if not token or token != AUTH_TOKEN:
        log_event("Token mismatch! Access denied.")
        return "Unauthorized: Invalid or missing token.", 403
    return render_template('remote.html')

@socketio.on('connect')
def handle_connect():
    client_token = request.args.get('token')
    client_ip = request.remote_addr
    
    # Strict Token Check
    if not client_token or client_token != AUTH_TOKEN:
        print(f"Rejected connection from {client_ip}: Invalid Token")
        disconnect()
        return

    log_event(f"Connection attempt: {client_ip}")
    
    # Add to devices list if it's not the local dashboard
    if client_ip != '127.0.0.1' and client_ip != HOST_IP:
        device = {'ip': client_ip, 'id': request.sid}
        CONNECTED_DEVICES.append(device)
        
        if client_ip not in TRUSTED_DEVICES:
            # Check if already in pending to avoid duplicates
            if not any(d['ip'] == client_ip for d in PENDING_DEVICES):
                PENDING_DEVICES.append(device)
            log_event(f"Device pending approval: {client_ip}")
        else:
            log_event(f"Trusted device connected: {client_ip} ({TRUSTED_DEVICES[client_ip]})")
            
        notify_gui()

@socketio.on('disconnect')
def handle_disconnect():
    global CONNECTED_DEVICES, PENDING_DEVICES
    client_ip = request.remote_addr
    CONNECTED_DEVICES = [d for d in CONNECTED_DEVICES if d['id'] != request.sid]
    PENDING_DEVICES = [d for d in PENDING_DEVICES if d['id'] != request.sid]
    
    log_event(f"Disconnected: {client_ip}")
    emit('update_devices', CONNECTED_DEVICES, broadcast=True)
    notify_gui()

def decode_lottery(payload):
    try:
        if len(payload) != 10:
            return None
        salt = payload[0]
        token_sum = sum(ord(c) for c in AUTH_TOKEN)
        # Index logic: (ord(salt) + token_sum) % 9 + 1
        # Range is 1-9 (0 is salt)
        real_index = (ord(salt) + token_sum) % 9 + 1
        return payload[real_index]
    except Exception:
        return None

@socketio.on('type_text')
def handle_type_text(data):
    if DEBUG_MODE:
        logger.debug(f"[type_text] Request from IP: {request.remote_addr} | Data: {data}")
        
    if not is_trusted(request):
        log_event(f"Untrusted type attempt from {request.remote_addr}")
        logger.warning(f"BLOCKED untrusted type_text attempt from {request.remote_addr}")
        return
    
    # Handle Lottery Obfuscation
    lottery_payload = data.get('lottery')
    if lottery_payload:
        if DEBUG_MODE:
            logger.debug(f"[type_text] Decoding Lottery payload: {lottery_payload}")
            
        real_char = decode_lottery(lottery_payload)
        if real_char:
            pyautogui.write(real_char)
        else:
            log_event("Failed to decode lottery payload")
            logger.error("[type_text] Failed to decode lottery payload")
        return

    # Fallback for non-obfuscated (or paste)
    text = data.get('text')
    if text:
        if DEBUG_MODE:
            logger.debug(f"[type_text] Typing raw text: {text}")
        pyautogui.write(text)

@socketio.on('paste_text')
def handle_paste_text(data):
    if DEBUG_MODE:
        logger.debug(f"[paste_text] Request from IP: {request.remote_addr} | Data: {data}")
        
    if not is_trusted(request):
        logger.warning(f"BLOCKED untrusted paste_text attempt from {request.remote_addr}")
        return
    text = data.get('text')
    if text:
        try:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            log_event("Pasted text to PC")
        except Exception as e:
            log_event(f"Paste error: {e}")
            logger.error(f"[paste_text] Exception: {e}")

@socketio.on('press_key')
def handle_press_key(data):
    if DEBUG_MODE:
        logger.debug(f"[press_key] Request from IP: {request.remote_addr} | Data: {data}")
        
    if not is_trusted(request):
        logger.warning(f"BLOCKED untrusted press_key attempt from {request.remote_addr}")
        return
    key = data.get('key')
    if key:
        if DEBUG_MODE:
            log_event(f"Key press: {key}")
        if key == 'undo':
            pyautogui.hotkey('ctrl', 'z')
        else:
            pyautogui.press(key)

@socketio.on('move_mouse')
def handle_move_mouse(data):
    if DEBUG_MODE:
        logger.debug(f"[move_mouse] Request from IP: {request.remote_addr} | Data: {data}")
        
    if not is_trusted(request):
        return
    dx = data.get('dx', 0)
    dy = data.get('dy', 0)
    pyautogui.moveRel(dx, dy)

@socketio.on('click_mouse')
def handle_click_mouse(data):
    if DEBUG_MODE:
        logger.debug(f"[click_mouse] Request from IP: {request.remote_addr} | Data: {data}")
        
    if not is_trusted(request):
        return
    button = data.get('button', 'left')
    pyautogui.click(button=button)

@socketio.on('hold_mouse')
def handle_hold_mouse(data):
    if DEBUG_MODE:
        logger.debug(f"[hold_mouse] Request from IP: {request.remote_addr} | Data: {data}")
        
    if not is_trusted(request):
        return
    button = data.get('button', 'left')
    action = data.get('action', 'down')
    
    if action == 'down':
        pyautogui.mouseDown(button=button)
    elif action == 'up':
        pyautogui.mouseUp(button=button)

def startup_health_check():
    """One-shot launch check: detect IP drift, verify firewall, log results."""
    global HOST_IP, HOST_URL
    
    current_ip = get_ip()
    last_ip = get_last_known_ip()
    checks_passed = True
    
    print("="*50)
    print("  STARTUP HEALTH CHECK")
    print("="*50)
    
    # --- 1. IP Drift Detection ---
    if last_ip and last_ip != current_ip:
        print(f"  [IP CHANGED] {last_ip} -> {current_ip}")
        logger.warning(f"IP address changed: {last_ip} -> {current_ip}")
        log_event(f"IP changed: {last_ip} -> {current_ip} (cert will regenerate)")
        HOST_IP = current_ip
        HOST_URL = f"https://{HOST_IP}:54321"
        checks_passed = False  # Will trigger cert regen via existing logic
    elif not last_ip:
        print(f"  [IP] First run detected. Current IP: {current_ip}")
        HOST_IP = current_ip
        HOST_URL = f"https://{HOST_IP}:54321"
    else:
        print(f"  [IP OK] {current_ip} (unchanged)")
    
    # Always ensure HOST_IP/HOST_URL match current reality
    if HOST_IP != current_ip:
        HOST_IP = current_ip
        HOST_URL = f"https://{HOST_IP}:54321"
    
    # Save current IP immediately
    save_config()
    
    # --- 2. Firewall Rule Verification (read-only check, no auto-modify) ---
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=RemoteKeyboard'],
            capture_output=True, text=True, timeout=5
        )
        if 'RemoteKeyboard' in result.stdout:
            print("  [FIREWALL OK] Rule 'RemoteKeyboard' exists")
        else:
            print("  [FIREWALL MISSING] No inbound rule for port 54321!")
            print("  -> Run 'allow_firewall.bat' as Admin to fix this.")
            logger.warning("Firewall rule 'RemoteKeyboard' not found. Phone connections will be blocked.")
            log_event("Firewall rule missing — run allow_firewall.bat to fix")
    except Exception as e:
        print(f"  [FIREWALL SKIP] Could not check firewall: {e}")
        logger.warning(f"Firewall check failed: {e}")
    
    # --- 3. Port Availability ---
    import socket as _socket
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            port_free = s.connect_ex(('localhost', 54321)) != 0
        if port_free:
            print("  [PORT OK] 54321 is available")
        else:
            print("  [PORT BUSY] 54321 is in use — another instance may be running")
            log_event("WARNING: Port 54321 already in use")
    except Exception:
        pass
    
    print("="*50)
    print(f"  Server URL: {HOST_URL}")
    print("="*50)
    
    return checks_passed

def start_server():
    load_config()
    startup_health_check()
    
    # Generate self-signed certs with proper SANs for LAN access
    def generate_self_signed_cert(cert_file, key_file):
        host_ip = get_ip()
        
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)
        cert = crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "State"
        cert.get_subject().L = "City"
        cert.get_subject().O = "RemoteKeyboard"
        cert.get_subject().OU = "Org"
        cert.get_subject().CN = host_ip  # Use LAN IP as CN
        cert.set_serial_number(int.from_bytes(os.urandom(8), 'big'))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(2*365*24*60*60)  # 2 years
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        
        # Add Subject Alternative Names (SANs) — required by modern browsers
        san_list = [
            f"IP:{host_ip}",
            "IP:127.0.0.1",
            "DNS:localhost",
            f"DNS:{host_ip}",
        ]
        san_extension = crypto.X509Extension(
            b"subjectAltName", False, ", ".join(san_list).encode()
        )
        cert.add_extensions([san_extension])
        
        cert.sign(k, 'sha256')
        
        with open(cert_file, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(key_file, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
        print(f"Generated new certificate with SANs: {', '.join(san_list)}")

    def cert_needs_regeneration(cert_file):
        """Check if the cert is missing SANs or doesn't match current IP."""
        if not os.path.exists(cert_file):
            return True
        try:
            with open(cert_file, 'rb') as f:
                cert_data = f.read()
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
            
            # Check if SANs exist
            has_san = False
            current_ip = get_ip()
            for i in range(cert.get_extension_count()):
                ext = cert.get_extension(i)
                if ext.get_short_name() == b'subjectAltName':
                    san_value = str(ext)
                    if current_ip in san_value:
                        has_san = True
                    break
            
            if not has_san:
                print(f"Certificate missing SANs for {current_ip}, regenerating...")
                return True
                
            return False
        except Exception as e:
            print(f"Error checking certificate: {e}")
            return True

    cert_path = 'cert.pem'
    key_path = 'key.pem'
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path) or cert_needs_regeneration(cert_path):
        print("Generating self-signed certificates...")
        generate_self_signed_cert(cert_path, key_path)

    print(f"Starting secure server on port 54321...")
    try:
        # Use ssl_context for Werkzeug (default dev server) compatibility
        socketio.run(app, host='0.0.0.0', port=54321, ssl_context=(cert_path, key_path), allow_unsafe_werkzeug=True, use_reloader=False)
    except TypeError:
        # Fallback if using eventlet/gevent which might prefer keyfile/certfile
        socketio.run(app, host='0.0.0.0', port=54321, keyfile=key_path, certfile=cert_path, use_reloader=False)
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == '__main__':
    print(f"Server starting...")
    print(f"Dashboard: {HOST_URL}")
    print(f"Token: {AUTH_TOKEN}")
    start_server()
