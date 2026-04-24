import paramiko

HOST = '119.91.117.232'
PORT = 22
USER = 'ubuntu'
PASS = 'Cbblly520+'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run_sudo(cmd, timeout=60):
    full_cmd = f'echo "{PASS}" | sudo -S bash -c \'{cmd}\''
    stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

# Check active nginx config
print('=== /etc/nginx/sites-enabled/guessr ===')
stdin, stdout, stderr = client.exec_command('cat /etc/nginx/sites-enabled/guessr 2>&1')
out = stdout.read().decode('utf-8', errors='replace')
print(out)

# Check if there are other configs
print('\n=== /etc/nginx/sites-enabled/ ===')
stdin, stdout, stderr = client.exec_command('ls -la /etc/nginx/sites-enabled/')
out = stdout.read().decode('utf-8', errors='replace')
print(out)

# Check main nginx.conf
print('\n=== /etc/nginx/nginx.conf (http section) ===')
stdin, stdout, stderr = client.exec_command('cat /etc/nginx/nginx.conf | grep -A5 "http {"')
out = stdout.read().decode('utf-8', errors='replace')
print(out)

# Test the actual routing behavior
print('\n=== Testing /api/ proxy ===')
out, err = run_sudo('curl -s -H "Host: 119.91.117.232" http://127.0.0.1/api/login-state')
print('With Host header:', out)

print('\n=== Testing without /api/ prefix ===')
out, err = run_sudo('curl -s -H "Host: 119.91.117.232" http://127.0.0.1/login-state')
print('Without /api/ prefix:', out)

client.close()
