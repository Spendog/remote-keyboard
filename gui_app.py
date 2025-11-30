import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from PIL import Image, ImageTk
import qrcode
import threading
import pystray
from pystray import MenuItem as item
import sys
import os
import app as server_app

class RemoteKeyboardGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Remote Keyboard")
        self.root.geometry("500x700")
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)
        
        # Load config immediately to ensure Token is correct for QR
        server_app.load_config()

        # Style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TLabel", background="#222", foreground="#fff", font=("Segoe UI", 10))
        self.style.configure("TFrame", background="#222")
        self.style.configure("TButton", background="#444", foreground="#fff")
        self.style.map("TButton", background=[('active', '#555')])
        
        self.root.configure(bg="#222")

        # Set icon
        try:
            if os.path.exists("icon.ico"):
                self.root.iconbitmap("icon.ico")
        except Exception as e:
            print(f"Error loading icon: {e}")

        # --- Header ---
        header_frame = ttk.Frame(root)
        header_frame.pack(pady=10)
        ttk.Label(header_frame, text="Remote Keyboard", font=("Segoe UI", 16, "bold")).pack()
        self.status_label = ttk.Label(header_frame, text="Server Running", foreground="#4caf50")
        self.status_label.pack()

        # --- Tabs ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Connect
        self.connect_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.connect_frame, text="Connect")
        self.setup_connect_tab()

        # Tab 2: Devices (Trusted/Pending)
        self.devices_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.devices_frame, text="Devices")
        self.setup_devices_tab()

        # Tab 3: Logs
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="Logs")
        self.setup_logs_tab()
        
        # Tab 4: Settings
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")
        self.setup_settings_tab()

        # --- Tray ---
        self.tray_icon = None
        
        # --- Start Server ---
        self.server_thread = threading.Thread(target=self.run_server, daemon=True)
        self.server_thread.start()

        # Register callback
        server_app.set_gui_callback(self.update_gui)

    def setup_connect_tab(self):
        # QR Code
        self.qr_label = ttk.Label(self.connect_frame)
        self.qr_label.pack(pady=20)
        self.generate_qr()

        # URL Info
        url_frame = ttk.Frame(self.connect_frame)
        url_frame.pack(pady=10, padx=20, fill='x')
        ttk.Label(url_frame, text="URL:").pack(anchor='w')
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.insert(0, f"{server_app.HOST_URL}/remote?token={server_app.AUTH_TOKEN}")
        self.url_entry.configure(state='readonly')
        self.url_entry.pack(fill='x', pady=5)

    def setup_devices_tab(self):
        # Pending
        ttk.Label(self.devices_frame, text="Pending Approval:", foreground="#ff9800").pack(pady=(10, 5), padx=10, anchor='w')
        self.pending_list = tk.Listbox(self.devices_frame, bg="#333", fg="#fff", height=4)
        self.pending_list.pack(padx=10, fill='x')
        
        btn_frame = ttk.Frame(self.devices_frame)
        btn_frame.pack(pady=5, padx=10, fill='x')
        ttk.Button(btn_frame, text="Approve Selected", command=self.approve_device).pack(side='left')

        # Connected/Trusted
        ttk.Label(self.devices_frame, text="Trusted Devices:", foreground="#4caf50").pack(pady=(20, 5), padx=10, anchor='w')
        self.trusted_list = tk.Listbox(self.devices_frame, bg="#333", fg="#fff", height=6)
        self.trusted_list.pack(padx=10, fill='x')
        
        # Management Buttons
        mgmt_frame = ttk.Frame(self.devices_frame)
        mgmt_frame.pack(pady=5, padx=10, fill='x')
        ttk.Button(mgmt_frame, text="Rename", command=self.rename_device).pack(side='left', padx=5)
        ttk.Button(mgmt_frame, text="Remove", command=self.remove_device).pack(side='left', padx=5)

    def setup_logs_tab(self):
        # Controls
        ctrl_frame = ttk.Frame(self.logs_frame)
        ctrl_frame.pack(pady=5, padx=10, fill='x')
        self.log_btn = ttk.Button(ctrl_frame, text="Stop Logging", command=self.toggle_logging)
        self.log_btn.pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Clear Logs", command=server_app.clear_cache).pack(side='left', padx=5)

        # Text Area
        self.log_text = tk.Text(self.logs_frame, bg="#1e1e1e", fg="#ccc", height=15, state='disabled')
        self.log_text.pack(padx=10, pady=5, fill='both', expand=True)

    def setup_settings_tab(self):
        ttk.Label(self.settings_frame, text="Customization").pack(pady=10, padx=10, anchor='w')
        ttk.Button(self.settings_frame, text="Change App Icon", command=self.change_icon).pack(padx=10, anchor='w')

    def generate_qr(self):
        url = f"{server_app.HOST_URL}/remote?token={server_app.AUTH_TOKEN}"
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        self.qr_image = ImageTk.PhotoImage(img)
        self.qr_label.configure(image=self.qr_image)

    def update_gui(self, state):
        self.root.after(0, lambda: self._process_update(state))

    def _process_update(self, state):
        # Update Pending
        self.pending_list.delete(0, tk.END)
        for dev in state['pending']:
            self.pending_list.insert(tk.END, dev['ip'])
            
        # Update Trusted
        self.trusted_list.delete(0, tk.END)
        # state['trusted'] is now a dict {ip: nickname}
        for ip, nickname in state['trusted'].items():
            status = "Connected" if any(d['ip'] == ip for d in state['connected']) else "Offline"
            display_text = f"{nickname} ({ip}) - {status}"
            self.trusted_list.insert(tk.END, display_text)

        # Update Logs
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        for entry in state['logs']:
            self.log_text.insert(tk.END, entry + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def approve_device(self):
        selection = self.pending_list.curselection()
        if selection:
            ip = self.pending_list.get(selection[0])
            server_app.approve_device(ip)
            
    def rename_device(self):
        selection = self.trusted_list.curselection()
        if selection:
            # Parse IP from "Nickname (IP) - Status"
            item_text = self.trusted_list.get(selection[0])
            # Simple extraction assuming format
            try:
                ip = item_text.split('(')[1].split(')')[0]
                new_name = tk.simpledialog.askstring("Rename Device", f"Enter new name for {ip}:")
                if new_name:
                    server_app.rename_device(ip, new_name)
            except IndexError:
                pass

    def remove_device(self):
        selection = self.trusted_list.curselection()
        if selection:
            item_text = self.trusted_list.get(selection[0])
            try:
                ip = item_text.split('(')[1].split(')')[0]
                if tk.messagebox.askyesno("Remove Device", f"Are you sure you want to remove {ip}?"):
                    server_app.remove_device(ip)
            except IndexError:
                pass

    def toggle_logging(self):
        if self.log_btn['text'] == "Stop Logging":
            server_app.toggle_logging(False)
            self.log_btn['text'] = "Start Logging"
        else:
            server_app.toggle_logging(True)
            self.log_btn['text'] = "Stop Logging"

    def change_icon(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.ico;*.jpg")])
        if file_path:
            try:
                img = Image.open(file_path)
                # Resize for window icon
                icon_img = ImageTk.PhotoImage(img)
                self.root.iconphoto(False, icon_img)
                # Save for tray
                self.custom_icon_path = file_path
            except Exception as e:
                print(f"Error loading icon: {e}")

    def check_port(self, port):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0

    def run_server(self):
        # Check if port is free before starting
        if not self.check_port(54321):
            print("Port 54321 is busy! Another instance might be running.")
            self.root.after(0, lambda: tk.messagebox.showerror("Error", "Port 54321 is in use.\nIs another instance running?"))
            self.root.after(100, self.quit_app, None, None)
            return
        server_app.start_server()

    def hide_window(self):
        self.root.withdraw()
        # Use custom icon if set, else default
        if hasattr(self, 'custom_icon_path'):
            image = Image.open(self.custom_icon_path)
        else:
            image = Image.new('RGB', (64, 64), color = 'red') # Placeholder
            
        menu = (item('Show', self.show_window), item('Quit', self.quit_app))
        self.tray_icon = pystray.Icon("name", image, "Remote Keyboard", menu)
        self.tray_icon.run()

    def show_window(self, icon, item):
        self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon, item):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = RemoteKeyboardGUI(root)
    root.mainloop()
