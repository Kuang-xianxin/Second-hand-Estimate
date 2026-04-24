import paramiko
import time

HOST = '119.91.117.232'
PORT = 22
USER = 'ubuntu'
PASS = 'Cbblly520+'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
transport = client.get_transport()
transport.set_keepalive(30)

def run_sudo(cmd, timeout=120):
    full_cmd = f'echo "{PASS}" | sudo -S bash -c \'{cmd}\''
    stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    return out, stderr.read().decode('utf-8', errors='replace')

def run_cmd(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    return out, ""

# Extract Chromium 145
print('Extracting Chromium 145...')
out, err = run_sudo('cd /tmp && unzip -q chrome-145.zip -d chromium145 2>&1; echo "Exit: $?"')
print(out[-200:])

# Find the chrome binary inside the extracted folder
out, _ = run_cmd('find /tmp/chromium145 -name "chrome" -type f 2>/dev/null')
print('\nChrome binary:', out.strip())

chrome_src = out.strip()

# Replace the chromium in /opt/guessr/
print('\nReplacing chromium in /opt/guessr/chromium/...')
out, err = run_sudo(f'rm -rf /opt/guessr/chromium_old && mv /opt/guessr/chromium /opt/guessr/chromium_old && mkdir -p /opt/guessr/chromium')
print(out)

# The chrome-linux folder from playwright has all needed files
out, err = run_sudo(f'mv /tmp/chromium145/chrome-linux /opt/guessr/chromium && chown -R ubuntu:ubuntu /opt/guessr/chromium && ls -la /opt/guessr/chromium/')
print(out)

# Verify chrome binary
out, _ = run_cmd('/opt/guessr/chromium/chrome-linux/chrome --version 2>&1')
print('\nChrome version:', out)

# Update .env
new_path = '/opt/guessr/chromium/chrome-linux/chrome'
print(f'\nUpdating .env to {new_path}...')
out, err = run_sudo(f'sed -i "s|PLAYWRIGHT_CHROMIUM_PATH=.*|PLAYWRIGHT_CHROMIUM_PATH={new_path}|" /opt/guessr/backend/.env')
print(out, err)

# Update systemd service
svc = f"""[Unit]
Description=Guessr Backend Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/guessr/backend
Environment="PATH=/opt/guessr/backend/venv/bin"
Environment="PLAYWRIGHT_CHROMIUM_PATH={new_path}"
ExecStart=/opt/guessr/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
import os
local_svc = os.path.join(os.path.dirname(__file__), 'guessr.service')
with open(local_svc, 'w') as f:
    f.write(svc)

sftp = client.open_sftp()
sftp.put(local_svc, '/tmp/guessr-backend.service')
sftp.close()

out, err = run_sudo('mv /tmp/guessr-backend.service /etc/systemd/system/guessr-backend.service && chmod 644 /etc/systemd/system/guessr-backend.service')
print('Updated systemd service')

# Restart backend
out, err = run_sudo('systemctl daemon-reload && systemctl restart guessr-backend')
print('Restarted backend')
time.sleep(6)

# Verify health
stdin, stdout, stderr = client.exec_command('curl -s http://127.0.0.1:8000/health')
out = stdout.read().decode('utf-8', errors='replace')
print('\nHealth:', out)

# Test playwright
print('\nTesting Playwright with Chromium 145...')
out, err = run_sudo('cd /opt/guessr/backend && venv/bin/python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); print(b.version); b.close(); p.stop()" 2>&1', timeout=30)
print('Playwright test:', out[-300:])

# Cleanup old chromium
out, err = run_sudo('rm -rf /opt/guessr/chromium_old /tmp/chrome-145.zip /tmp/chromium145 2>/dev/null; echo cleaned')
print('\nCleaned up:', out)

print('\nDONE')
client.close()
