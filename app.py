from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect
import pyautogui
import socket
import qrcode
import io
import base64
import secrets
import logging
import datetime
import json
import pyperclip
import os
from OpenSSL import crypto

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# Security Token
AUTH_TOKEN = secrets.token_urlsafe(16)
CONNECTED_DEVICES = []

# State
TRUSTED_DEVICES = set()
PENDING_DEVICES = [] # List of dicts
LOG_CACHE = []
LOGGING_ENABLED = True
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
# We will use port 5000 and HTTPS
HOST_URL = f"https://{HOST_IP}:5000"

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
            'trusted': list(TRUSTED_DEVICES),
            'logs': LOG_CACHE[-50:] # Send last 50 logs
        }
        gui_callback(state)

def log_event(message):
    if LOGGING_ENABLED:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        LOG_CACHE.append(entry)
        # Keep cache from growing indefinitely
        if len(LOG_CACHE) > 1000:
            LOG_CACHE.pop(0)
        notify_gui()

def load_config():
    global TRUSTED_DEVICES
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                TRUSTED_DEVICES = set(data.get('trusted_devices', []))
                print(f"Loaded {len(TRUSTED_DEVICES)} trusted devices.")
        except Exception as e:
            print(f"Error loading config: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'trusted_devices': list(TRUSTED_DEVICES)}, f)
    except Exception as e:
        print(f"Error saving config: {e}")

def approve_device(ip):
    TRUSTED_DEVICES.add(ip)
    save_config()
    # Remove from pending if there
    global PENDING_DEVICES
    PENDING_DEVICES = [d for d in PENDING_DEVICES if d['ip'] != ip]
    log_event(f"Device approved: {ip}")
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
    if not token or token != AUTH_TOKEN:
        return "Unauthorized: Invalid or missing token.", 403
    return render_template('remote.html')

@socketio.on('connect')
def handle_connect():
    client_token = request.args.get('token')
    client_ip = request.remote_addr
    
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
            log_event(f"Trusted device connected: {client_ip}")
            
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

@socketio.on('type_text')
def handle_type_text(data):
    if not is_trusted(request):
        return
    text = data.get('text')
    if text:
        pyautogui.write(text)

@socketio.on('paste_text')
def handle_paste_text(data):
    if not is_trusted(request):
        return
    text = data.get('text')
    if text:
        try:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            log_event("Pasted text to PC")
        except Exception as e:
            log_event(f"Paste error: {e}")

@socketio.on('press_key')
def handle_press_key(data):
    if not is_trusted(request):
        return
    key = data.get('key')
    if key:
        pyautogui.press(key)

@socketio.on('move_mouse')
def handle_move_mouse(data):
    if not is_trusted(request):
        return
    dx = data.get('dx', 0)
    dy = data.get('dy', 0)
    pyautogui.moveRel(dx, dy)

@socketio.on('click_mouse')
def handle_click_mouse(data):
    if not is_trusted(request):
        return
    button = data.get('button', 'left')
    pyautogui.click(button=button)

def start_server():
    load_config()
    
    # Generate self-signed certs if not exist
    def generate_self_signed_cert(cert_file, key_file):
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)
        cert = crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "State"
        cert.get_subject().L = "City"
        cert.get_subject().O = "RemoteKeyboard"
        cert.get_subject().OU = "Org"
        cert.get_subject().CN = "localhost"
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365*24*60*60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha256')
        
        with open(cert_file, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(key_file, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    cert_path = 'cert.pem'
    key_path = 'key.pem'
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("Generating self-signed certificates...")
        generate_self_signed_cert(cert_path, key_path)

    print(f"Starting secure server on port 5000...")
    try:
        socketio.run(app, host='0.0.0.0', port=5000, keyfile=key_path, certfile=cert_path)
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == '__main__':
    print(f"Server starting...")
    print(f"Dashboard: {HOST_URL}")
    print(f"Token: {AUTH_TOKEN}")
    start_server()
