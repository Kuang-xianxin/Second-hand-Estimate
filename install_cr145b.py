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

# Step 1: Re-download chromium 145 (redirect to Google Storage)
print('Re-downloading Chromium 145...')
out, err = run_sudo('cd /tmp && wget --progress=dot:giga -O chrome-145.zip "https://storage.googleapis.com/chrome-for-testing-public/145.0.7632.6/linux64/chrome-linux64.zip" 2>&1; ls -lh /tmp/chrome-145.zip 2>/dev/null', timeout=300)
print(out[-300:])

# Step 2: Extract
print('\nExtracting...')
out, err = run_sudo('cd /tmp && unzip -q chrome-145.zip -d chromium145 2>&1; echo "Exit: $?"')
print(out[-100:])

# Step 3: Verify
out, _ = run_cmd('find /tmp/chromium145 -name "chrome" -type f 2>/dev/null')
print('\nChrome binary:', out.strip())

chrome_path = out.strip()
if not chrome_path:
    print('ERROR: Chrome binary not found!')
    client.close()
    exit(1)

# Step 4: Move to /opt/guessr/chromium (replace existing)
print('\nInstalling to /opt/guessr/chromium/...')
out, err = run_sudo(f'rm -rf /opt/guessr/chromium && mv /tmp/chromium145 /opt/guessr/chromium && chown -R ubuntu:ubuntu /opt/guessr/chromium')
print(out, err)

# Verify
out, _ = run_cmd(f'{chrome_path} --version 2>&1')
print('\nChrome version:', out.strip())

# Update .env
correct_path = chrome_path
print(f'\nUpdating .env to: {correct_path}')
out, err = run_sudo(f'sed -i "s|PLAYWRIGHT_CHROMIUM_PATH=.*|PLAYWRIGHT_CHROMIUM_PATH={correct_path}|" /opt/guessr/backend/.env')

# Update systemd service
svc = f"""[Unit]
Description=Guessr Backend Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/guessr/backend
Environment="PATH=/opt/guessr/backend/venv/bin"
Environment="PLAYWRIGHT_CHROMIUM_PATH={correct_path}"
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

# Restart backend
print('\nRestarting backend...')
out, err = run_sudo('systemctl daemon-reload && systemctl restart guessr-backend')
time.sleep(6)

# Health
stdin, stdout, stderr = client.exec_command('curl -s http://127.0.0.1:8000/health')
out = stdout.read().decode('utf-8', errors='replace')
print('Health:', out)

# Playwright test
print('\nPlaywright test:')
out, err = run_sudo(f'cd /opt/guessr/backend && venv/bin/python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); v = b.version; print(v); b.close(); p.stop()" 2>&1', timeout=30)
print(out[-300:])

# Cleanup zip
out, err = run_sudo('rm -f /tmp/chrome-145.zip && echo cleaned')
print('\nCleanup:', out)

print('\nDONE')
client.close()
