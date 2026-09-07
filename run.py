"""
Vitala 一键启动（v2.2）
- 若 8001 已有 Vitala 在运行 -> 直接打开浏览器，不重复启动
- 若 8001 被其他程序占用 -> 自动改用下一个可用端口
- 检测到 cloudflared 时自动生成公网链接
"""

import os
import re
import sys
import time
import socket
import subprocess
import threading
import urllib.request
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

PORT = int(os.getenv("VITALA_PORT", "8001"))
CLOUDFLARED_EXE = os.path.join(PROJECT_ROOT, "cloudflared.exe")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def port_busy(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.6):
            return True
    except OSError:
        return False


def is_vitala_running(port):
    """本机该端口上是否已是 Vitala"""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/",
            headers={"User-Agent": "Vitala-Launcher"},
        )
        with urllib.request.urlopen(req, timeout=2.5) as r:
            head = r.read(600)
            return b"Vitala" in head
    except Exception:
        return False


def find_cloudflared():
    if os.path.exists(CLOUDFLARED_EXE):
        return CLOUDFLARED_EXE
    try:
        from shutil import which
        return which("cloudflared") or None
    except Exception:
        return None


def start_server(port):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    import uvicorn
    from src.api import app
    print(f"  服务启动中（端口 {port}），首次运行需加载知识库，请稍候…")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def start_tunnel(exe, port):
    """用 cloudflared 快速隧道生成公网链接（无需注册账号）"""
    time.sleep(8)
    url_file = os.path.join(PROJECT_ROOT, "public_url.txt")
    print("\n  正在生成公网链接（cloudflared quick tunnel）…")
    try:
        proc = subprocess.Popen(
            [exe, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception as e:
        print(f"  公网链接启动失败: {e}")
        return

    pattern = re.compile(r"https://(?!api\.)[a-z0-9-]{4,}\.trycloudflare\.com")
    found = None
    try:
        for line in proc.stdout:
            m = pattern.search(line or "")
            if m:
                found = m.group(0)
                break
    except Exception:
        pass

    if found:
        with open(url_file, "w", encoding="utf-8") as f:
            f.write(found + "\n")
        print("\n" + "=" * 60)
        print("  Vitala is LIVE!")
        print("=" * 60)
        print(f"\n  本机访问 : http://localhost:{port}")
        print(f"  局域网   : http://{get_local_ip()}:{port}")
        print(f"  公网链接 : {found}")
        print("\n  把上面的公网链接发给任何人，对方打开即可注册使用")
        print("  （保持本窗口运行，链接才有效）")
        print("=" * 60 + "\n")
        webbrowser.open(found)
    else:
        print(f"\n  未能读取到公网链接，请稍后查看上面的 trycloudflare.com 地址")
        print("  或双击「一键公网分享.bat」重新尝试")
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass


def main():
    print("=" * 60)
    print("  Vitala — AI Nutrition Companion")
    print("  你的个性化 AI 营养管家")
    print("=" * 60)

    # 情况 1：Vitala 已经在运行 -> 直接打开，不重复启动
    if is_vitala_running(PORT):
        print(f"\n  ✔ Vitala 已经在运行: http://localhost:{PORT}")
        print("  无需重复启动，直接打开浏览器…")
        webbrowser.open(f"http://localhost:{PORT}")
        print("\n  提示：如果页面还是旧样式，请按 Ctrl+F5 强制刷新。")
        try:
            input("\n  按回车键关闭本窗口…")
        except EOFError:
            pass
        return

    # 情况 2：端口被其他程序占用 -> 自动找下一个可用端口
    port = PORT
    if port_busy(port):
        for candidate in range(PORT + 1, PORT + 30):
            if not port_busy(candidate):
                port = candidate
                break
        else:
            print(f"\n  [错误] 端口 {PORT}-{PORT+29} 均被占用，无法启动。")
            input("按回车键退出…")
            return
        print(f"\n  [提示] 端口 {PORT} 被其他程序占用，已改用端口 {port}")

    exe = find_cloudflared()
    if exe is None:
        print("\n  未检测到 cloudflared：本机可正常使用。")
        print("  想生成“发给别人打开”的公网链接？双击「一键公网分享.bat」即可。\n")
    else:
        threading.Thread(target=lambda: start_tunnel(exe, port), daemon=True).start()

    print(f"\n  [1/2] 正在本机启动服务: http://localhost:{port}\n")
    try:
        start_server(port)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()