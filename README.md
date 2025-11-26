# Remote Keyboard & Mouse

Turn your smartphone into a remote keyboard and trackpad for your PC. Control your computer from across the room with low latency and a clean, dark-mode interface.

## Features (v1.2)

*   **Remote Control**: Use your phone as a wireless keyboard and mouse trackpad.
*   **Buffered Input Mode**: Type with full autocorrect and predictive text on your phone, then send the message in one go. Perfect for long messages.
*   **Smart Throttling**: Optimized mouse movement for smooth performance over Wi-Fi.
*   **Custom Shortcuts**: Create a desktop shortcut with your own custom PNG icon using the included script.
*   **Secure Pairing**: Uses a token-based QR code system to ensure only you can control your PC.

## Installation

1.  **Clone or Download** this repository.
2.  **Run Setup**: Double-click `setup.bat` to install Python dependencies automatically.
    *   *Note: Requires Python 3.12+ installed and added to PATH.*

## Usage

1.  **Start the App**: Double-click `run.bat`.
2.  **Connect**:
    *   A QR code will appear on your screen.
    *   Scan it with your phone's camera.
    *   Open the link to start controlling your PC.
3.  **Buffered Mode**:
    *   Toggle the "Buffered" checkbox in the app to enable autocorrect.
    *   Type your message and hit "Send" (Green button).

## Custom Shortcut

Want a fancy icon on your desktop?
1.  Run `create_shortcut_advanced.py` (or use the command line).
2.  Select a PNG image when prompted.
3.  A shortcut will be created on your Desktop. Right-click and "Pin to Taskbar" if desired!

## Troubleshooting

*   **Firewall**: If you can't connect, ensure "Python" is allowed through your Windows Firewall on Private Networks.
*   **Same Network**: Your phone and PC must be on the same Wi-Fi network.
