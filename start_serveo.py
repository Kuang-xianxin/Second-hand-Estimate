"""
使用 serveo.net 进行内网穿透（通过 SSH，不需要注册）
"""
import subprocess
import time
import sys

def start_serveo_tunnel(local_port, remote_name):
    """启动 serveo 隧道"""
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=60",
        "-R", f"80:localhost:{local_port}",
        f"{remote_name}@serveo.net"
    ]

    print(f"启动 serveo 隧道: {remote_name} -> localhost:{local_port}")

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        startupinfo=startupinfo,
        text=True
    )

    return process

def main():
    print("=" * 50)
    print("使用 serveo.net 进行内网穿透...")
    print("注意: 需要系统中已安装 SSH 客户端")
    print("=" * 50)

    # 启动前端隧道
    print("\n启动前端隧道 (端口 5173)...")
    frontend_process = start_serveo_tunnel(5173, "guessr-frontend")

    # 启动后端隧道
    print("\n启动后端隧道 (端口 8000)...")
    backend_process = start_serveo_tunnel(8000, "guessr-backend")

    print("\n" + "=" * 50)
    print("隧道启动命令已执行!")
    print("前端地址: https://guessr-frontend.serveo.net")
    print("后端地址: https://guessr-backend.serveo.net")
    print("=" * 50)
    print("\n按 Ctrl+C 停止隧道")

    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止隧道...")
        frontend_process.terminate()
        backend_process.terminate()
        print("已停止")

if __name__ == "__main__":
    main()
