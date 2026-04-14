"""
内网穿透脚本 - 使用 ngrok 将本地服务暴露到公网
这样浏览器测试代理就可以访问 localhost 了
"""
import os
import json
import time
import subprocess
import requests
import sys

NGROK_PATH = r"C:\Users\QQ276\AppData\Local\Temp\ngrok\ngrok.exe"
FRONTEND_PORT = 5173
BACKEND_PORT = 8000
NGROK_API_URL = "http://localhost:4040/api/tunnels"

def check_ngrok():
    """检查 ngrok 是否存在"""
    if not os.path.exists(NGROK_PATH):
        print("正在下载 ngrok...")
        download_cmd = [
            "powershell", "-Command",
            f"Invoke-WebRequest -Uri 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip' -OutFile '$env:TEMP\\ngrok.zip' -UseBasicParsing"
        ]
        subprocess.run(download_cmd, check=True)

        extract_cmd = [
            "powershell", "-Command",
            f"Expand-Archive -Path '$env:TEMP\\ngrok.zip' -DestinationPath '$env:TEMP\\ngrok' -Force"
        ]
        subprocess.run(extract_cmd, check=True)
        print("ngrok 下载完成")

def start_tunnel(port, name):
    """启动 ngrok 隧道"""
    cmd = [
        NGROK_PATH, "http", str(port),
        "--log", "stdout",
        "--metadata", f'"name":"{name}"'
    ]

    # 使用 CREATE_NO_WINDOW 避免弹出窗口
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo
    )
    return process

def get_tunnel_url():
    """获取当前隧道 URL"""
    try:
        response = requests.get(NGROK_API_URL, timeout=5)
        data = response.json()
        tunnels = data.get('tunnels', [])
        if tunnels:
            # 返回 https URL
            for t in tunnels:
                if t.get('proto') == 'https':
                    return t.get('public_url')
            return tunnels[0].get('public_url')
    except Exception as e:
        print(f"获取隧道 URL 失败: {e}")
    return None

def main():
    print("=" * 50)
    print("内网穿透启动中...")
    print("=" * 50)

    check_ngrok()

    # 检查 ngrok 是否已经在运行
    existing_url = get_tunnel_url()
    if existing_url:
        print(f"检测到 ngrok 已在运行，URL: {existing_url}")
        return existing_url

    # 启动前端隧道
    print(f"正在启动前端隧道 (端口 {FRONTEND_PORT})...")
    frontend_process = start_tunnel(FRONTEND_PORT, "frontend")

    # 等待 ngrok 启动
    time.sleep(3)

    # 获取 URL
    frontend_url = get_tunnel_url()
    if frontend_url:
        print(f"前端隧道已启动: {frontend_url}")
    else:
        print("前端隧道启动失败，尝试继续...")

    # 启动后端隧道
    print(f"正在启动后端隧道 (端口 {BACKEND_PORT})...")
    backend_process = start_tunnel(BACKEND_PORT, "backend")

    time.sleep(3)

    backend_url = get_tunnel_url()
    if backend_url:
        print(f"后端隧道已启动: {backend_url}")

    print()
    print("=" * 50)
    print("内网穿透完成！")
    print(f"前端地址: {frontend_url}")
    print(f"后端地址: {backend_url}")
    print("=" * 50)

    # 保存 URL 到文件供后续使用
    with open("tunnel_urls.json", "w") as f:
        json.dump({
            "frontend": frontend_url,
            "backend": backend_url,
            "timestamp": time.time()
        }, f, indent=2)

    return frontend_url, backend_url

if __name__ == "__main__":
    main()
