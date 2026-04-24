import paramiko
import os

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

# Write the fixed nginx config
nginx_conf = """server {
    listen 80;
    server_name 119.91.117.232;

    root /var/www/guessr;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        chunked_transfer_encoding on;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
"""

print('Uploading fixed nginx config...')
local_nginx = os.path.join(os.path.dirname(__file__), 'guessr_nginx_fixed.conf')
with open(local_nginx, 'w', encoding='utf-8') as f:
    f.write(nginx_conf)

sftp = client.open_sftp()
sftp.put(local_nginx, '/tmp/guessr_nginx_fixed.conf')
sftp.close()

out, err = run_sudo('mv /tmp/guessr_nginx_fixed.conf /etc/nginx/sites-available/guessr && chmod 644 /etc/nginx/sites-available/guessr')
print(out, err)

# Test
out, err = run_sudo('nginx -t')
print('NGINX TEST:', out)
if err.strip():
    print('ERR:', err[-300:])

# Reload
out, err = run_sudo('systemctl reload nginx')
print('RELOAD:', out, err)

# Verify routing works
print('\nVerifying /api/login-state routes correctly...')
out, err = run_sudo('curl -s http://127.0.0.1/api/login-state')
print('Response:', out)

client.close()
print('\nDONE')
