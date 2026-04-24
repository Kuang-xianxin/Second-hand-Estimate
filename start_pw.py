import paramiko
import time
import threading

HOST = '119.91.117.232'
PORT = 22
USER = 'ubuntu'
PASS = 'Cbblly520+'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
transport = client.get_transport()
transport.set_keepalive(30)

def run_sudo_no_wait(cmd):
    """Run command without waiting for output - fire and forget"""
    full_cmd = f'echo "{PASS}" | sudo -S bash -c \'{cmd}\''
    transport = client.get_transport()
    channel = transport.open_session()
    channel.exec_command(full_cmd)
    # Don't wait for output - fire and forget

# Check if playwright is already being installed
stdin, stdout, stderr = client.exec_command('ps aux | grep playwright | grep -v grep')
out = stdout.read().decode('utf-8', errors='replace')
print('Current playwright processes:', out)

# Check if chromium is already installed
stdin, stdout, stderr = client.exec_command('find /root/.cache/ms-playwright -name "chrome" -type f 2>/dev/null | head -5')
out = stdout.read().decode('utf-8', errors='replace')
print('Existing chromium:', out)

# Start install in background - no waiting
print('\nStarting playwright install (fire and forget)...')
run_sudo_no_wait('cd /opt/guessr/backend && nohup /opt/guessr/backend/venv/bin/python -m playwright install chromium > /tmp/pw_install.log 2>&1 &')
print('Install started!')

# Wait a bit then check status
time.sleep(5)
stdin, stdout, stderr = client.exec_command('ps aux | grep "playwright install" | grep -v grep')
out = stdout.read().decode('utf-8', errors='replace')
print('Playwright install running:', bool(out.strip()))

# Check log
stdin, stdout, stderr = client.exec_command('cat /tmp/pw_install.log 2>/dev/null | tail -10')
out = stdout.read().decode('utf-8', errors='replace')
print('Install log:', out)

print('\nPlaywright download is running on the server in background.')
print('You can check progress with: ssh ubuntu@119.91.117.232 "tail -f /tmp/pw_install.log"')
client.close()
