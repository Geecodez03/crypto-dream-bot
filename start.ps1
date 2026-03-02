# Stop existing processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Clear port 5000
netsh int ipv4 set dynamicport tcp start=49152 num=16384 | Out-Null

# Set environment variables
$env:FLASK_APP = "main.py"
$env:FLASK_DEBUG = "1"

# Start the server
python main.py
