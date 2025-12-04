@echo off
echo Requesting Admin Privileges to Open Port 54321...
netsh advfirewall firewall add rule name="RemoteKeyboard" dir=in action=allow protocol=TCP localport=54321
echo.
echo Done! If you see "Ok.", the port is open.
pause
