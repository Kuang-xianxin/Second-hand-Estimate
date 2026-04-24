import paramiko

HOST = '119.91.117.232'
PORT = 22
USER = 'ubuntu'
PASS = 'Cbblly520+'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
transport = client.get_transport()
transport.set_keepalive(30)

def run_cmd(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

# Check if storage state file exists
print('=== Storage State File ===')
out, err = run_cmd('ls -la /opt/guessr/backend/xianyu_storage_state.json 2>&1')
print(out, err)

# Test /api/login-state endpoint
print('\n=== /api/login-state ===')
out, err = run_cmd('curl -s http://127.0.0.1:8000/api/login-state')
print(out, err)

# Test /api/open-xianyu-login endpoint (without auth)
print('\n=== /api/open-xianyu-login (no auth) ===')
out, err = run_cmd('curl -s -w "\\nHTTP_CODE:%{http_code}" http://127.0.0.1:8000/api/open-xianyu-login -X POST')
print(out, err)

# Test /api/open-xianyu-login endpoint (with auth)
print('\n=== /api/open-xianyu-login (with auth) ===')
out, err = run_cmd('curl -s -w "\\nHTTP_CODE:%{http_code}" -H "Authorization: Bearer test" http://127.0.0.1:8000/api/open-xianyu-login -X POST')
print(out, err)

# Check recent backend logs
print('\n=== Recent Backend Logs ===')
out, err = run_cmd('journalctl -u guessr-backend --no-pager -n 20 2>&1 | tail -20')
print(out)

# Check backend process
print('\n=== Backend Process ===')
out, err = run_cmd('ps aux | grep uvicorn | grep -v grep')
print(out)

# Check which llm.py is actually running (check for Claude references)
print('\n=== Checking if Claude code exists in running backend ===')
out, err = run_cmd('grep -l "anthropic" /opt/guessr/backend/app/services/llm.py 2>&1')
print(out, err)

# Verify config
print('\n=== Config check ===')
out, err = run_cmd('head -5 /opt/guessr/backend/app/config.py')
print(out)

print('\n=== .env check ===')
out, err = run_cmd('head -5 /opt/guessr/backend/.env')
print(out)

client.close()
