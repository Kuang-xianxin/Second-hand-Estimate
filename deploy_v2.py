"""
部署脚本 v2 - 处理编码问题，使用英文路径
"""
import paramiko
import time
import os
import tarfile
import io

HOST = '119.91.117.232'
PORT = 22
USER = 'ubuntu'
PASS = 'Cbblly520+'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=30)
print('SSH connected')

transport = client.get_transport()
transport.set_keepalive(30)

def run_sudo(cmd, timeout=120):
    full_cmd = f'echo "{PASS}" | sudo -S bash -c \'{cmd}\''
    stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def run_cmd(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

# ===== Step 1: Clean up apt lock =====
print('\n===== Step 1: Clean up apt lock =====')
# Kill the old apt process
out, err = run_sudo('kill -9 12552 2>/dev/null; sleep 2; rm -f /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock /var/cache/apt/archives/lock 2>/dev/null; dpkg --configure -a', timeout=60)
print(out[-500:])
if err.strip():
    print('ERR:', err[-300:])

# Install packages
print('\n===== Install packages =====')
out, err = run_sudo('apt update && apt install -y python3-pip python3-venv nginx curl', timeout=300)
print(out[-500:])
if err.strip():
    print('ERR:', err[-500:])

# Verify
out, err = run_cmd('which nginx && which python3 && nginx -v 2>&1')
print('VERIFY:', out)

# ===== Step 2: Setup directories (English names) =====
print('\n===== Step 2: Setup directories =====')
out, err = run_sudo('mkdir -p /var/www/guessr && mkdir -p /opt/guessr/backend && mkdir -p /tmp/guessr-backend && mkdir -p /tmp/guessr-frontend && chown -R ubuntu:ubuntu /var/www/guessr /opt/guessr')
print(out)
if err.strip():
    print('ERR:', err)

# ===== Step 3: Pack and upload code =====
print('\n===== Step 3: Pack and upload code =====')

# Pack frontend
frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
frontend_tar = io.BytesIO()
with tarfile.open(fileobj=frontend_tar, mode='w:gz') as tar:
    for root, dirs, files in os.walk(frontend_dir):
        for file in files:
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, frontend_dir)
            tar.add(filepath, arcname=arcname)
frontend_tar.seek(0)
print(f'Frontend tar: {len(frontend_tar.getvalue())} bytes')

# Pack backend (exclude large files)
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
exclude_names = {'node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'out.txt', '__pycache__'}
exclude_suffixes = {'.pyc', '.db', '.sqlite'}

backend_tar = io.BytesIO()
with tarfile.open(fileobj=backend_tar, mode='w:gz') as tar:
    for root, dirs, files in os.walk(backend_dir):
        dirs[:] = [d for d in dirs if d not in exclude_names]
        for file in files:
            if any(file.endswith(s) for s in exclude_suffixes):
                continue
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, backend_dir)
            tar.add(filepath, arcname=arcname)
backend_tar.seek(0)
print(f'Backend tar: {len(backend_tar.getvalue())} bytes')

# Upload
print('Uploading frontend...')
sftp = client.open_sftp()
sftp.putfo(frontend_tar, '/tmp/guessr-frontend.tar.gz')
sftp.close()

print('Uploading backend...')
sftp = client.open_sftp()
sftp.putfo(backend_tar, '/tmp/guessr-backend.tar.gz')
sftp.close()

# Extract to temp dirs
print('Extracting...')
out, err = run_sudo('cd /tmp && tar -xzf guessr-frontend.tar.gz -C /tmp/guessr-frontend/ && tar -xzf guessr-backend.tar.gz -C /tmp/guessr-backend/ && ls /tmp/guessr-frontend/ && ls /tmp/guessr-backend/')
print(out[-600:])
if err.strip():
    print('ERR:', err[-300:])

# Move to target dirs
print('Moving to target directories...')
out, err = run_sudo('cp -r /tmp/guessr-frontend/* /var/www/guessr/ && cp -r /tmp/guessr-backend/* /opt/guessr/backend/')
print(out)
if err.strip():
    print('ERR:', err)

# Fix permissions
out, err = run_sudo('chown -R ubuntu:ubuntu /var/www/guessr && chown -R ubuntu:ubuntu /opt/guessr')
print(out)

# Verify
out, err = run_cmd('ls /var/www/guessr/ && echo "---" && ls /opt/guessr/backend/')
print('Frontend files:', out[:300])
print('Backend files:', out[300:])

# ===== Step 4: Install Python venv =====
print('\n===== Step 4: Install Python venv =====')
out, err = run_sudo('apt install -y python3.10-venv', timeout=120)
print(out[-300:])
if err.strip():
    print('ERR:', err[-200:])

out, err = run_sudo('cd /opt/guessr/backend && su ubuntu -c "python3 -m venv venv"', timeout=120)
print(out)
if err.strip():
    print('ERR:', err[-300:])

# Install pip packages
pip_cmd = 'cd /opt/guessr/backend && su ubuntu -c "venv/bin/pip install --upgrade pip" && ' \
          'cd /opt/guessr/backend && su ubuntu -c "venv/bin/pip install fastapi uvicorn[standard] sqlalchemy aiosqlite httpx beautifulsoup4 requests python-dotenv pydantic pydantic-settings python-multipart"'
out, err = run_sudo(pip_cmd, timeout=600)
print(out[-1000:])
if err.strip():
    print('ERR:', err[-500:])

# ===== Step 5: Write .env =====
print('\n===== Step 5: Write .env =====')
backend_env = """DEEPSEEK_API_KEY=sk-e415e09f80fa49009d9f11f02e4b9ec3
QWEN_API_KEY=sk-3069d81f5d944540859a245503fa4693
DOUBAO_API_KEY=17f077f8-39a1-4059-b867-d62b15d2daa2
DEEPSEEK_MODEL=deepseek-chat
QWEN_MODEL=qwen-max
QWEN_VISION_MODEL=qwen-vl-max
QWEN_VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode
DOUBAO_MODEL=ep-m-20260327193150-m6442
DOUBAO_VISION_MODEL=ep-m-20260327193150-m6442
DEEPSEEK_BASE_URL=https://api.deepseek.com
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_VISION_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_TIMEOUT_SECONDS=30
DATABASE_URL=sqlite+aiosqlite:///./guessr.db
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:5173
CRAWL_INTERVAL_SECONDS=300
MAX_ITEMS_PER_QUERY=60
BARGAIN_THRESHOLD=120
"""
env_escaped = backend_env.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
env_cmd = f'cat > /opt/guessr/backend/.env << \'ENVEOF\'\n{backend_env}ENVEOF\nchown ubuntu:ubuntu /opt/guessr/backend/.env\nchmod 600 /opt/guessr/backend/.env'
out, err = run_sudo(env_cmd)
print(out)
if err.strip():
    print('ENV ERR:', err[-300:])

out, err = run_cmd('head -3 /opt/guessr/backend/.env')
print('.env content:', out)

# ===== Step 6: Nginx ======
print('\n===== Step 6: Nginx =====')
nginx_conf = """server {
    listen 80;
    server_name 119.91.117.232;

    root /var/www/guessr;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
"""
nginx_escaped = nginx_conf.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
nginx_cmd = f'cat > /etc/nginx/sites-available/guessr << \'NGINXEOF\'\n{nginx_conf}NGINXEOF\nln -sf /etc/nginx/sites-available/guessr /etc/nginx/sites-enabled/\nrm -f /etc/nginx/sites-enabled/default\nnginx -t'
out, err = run_sudo(nginx_cmd)
print(out)
if err.strip():
    print('NGINX ERR:', err[-500:])

out, err = run_sudo('systemctl reload nginx')
print(out, err)

# ===== Step 7: systemd service =====
print('\n===== Step 7: systemd service =====')
service_conf = """[Unit]
Description=Guessr Backend Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/guessr/backend
Environment="PATH=/opt/guessr/backend/venv/bin"
ExecStart=/opt/guessr/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
svc_cmd = f'cat > /etc/systemd/system/guessr-backend.service << \'SVCEOF\'\n{service_conf}SVCEOF\nsystemctl daemon-reload\nsystemctl enable guessr-backend\nsystemctl start guessr-backend'
out, err = run_sudo(svc_cmd)
print(out)
if err.strip():
    print('SVC ERR:', err[-500:])

time.sleep(5)

# ===== Step 8: Verify =====
print('\n===== Step 8: Verify =====')

out, err = run_cmd('systemctl status guessr-backend --no-pager 2>&1 | head -30')
print('Service status:', out)

out, err = run_cmd('ss -tlnp | grep -E ":(8000|80)"')
print('Ports:', out)

out, err = run_cmd('curl -s http://127.0.0.1:8000/health 2>&1')
print('Backend health:', out)
if err.strip():
    print('ERR:', err)

out, err = run_cmd('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/')
print('Frontend HTTP:', out)

print('\n===== DONE =====')
print('Access: http://119.91.117.232')

client.close()
