# Stop existing processes
Get-Process python | Stop-Process -Force -ErrorAction SilentlyContinue

# Clear port
netsh int ipv4 set dynamicport tcp start=49152 num=16384 | Out-Null

# Set modern Flask variables
$env:FLASK_DEBUG = "1"
$env:FLASK_APP = "main.py"

# Start with clean output
python main.py
