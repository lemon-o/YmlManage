import os
import sys
import time
import socket
import threading
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional
import urllib.request

# 设置控制台 utf-8 编码并对特殊字符做容错，防止在某些 Windows 终端下编码异常
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保以当前根目录为基准
CURRENT_DIR = Path(__file__).resolve().parent
os.chdir(CURRENT_DIR)
sys.path.insert(0, str(CURRENT_DIR))


def get_lan_ip() -> str:
    """获取本机在局域网中的 IPv4 地址"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('223.5.5.5', 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_pid_occupying_port(port: int) -> Optional[int]:
    """获取占用指定端口的进程 PID"""
    try:
        output = subprocess.check_output(
            f'netstat -ano | findstr ":{port}"',
            shell=True,
            encoding="gbk",
            errors="ignore"
        )
        for line in output.strip().splitlines():
            parts = line.split()
            # 格式例如: TCP 0.0.0.0:8080 0.0.0.0:0 LISTENING 1234
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
                return int(parts[4])
    except Exception:
        pass
    return None


def is_yml_manage_running(port: int) -> bool:
    """检测当前端口是否正在运行 YmlManage 服务"""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/profiles",
            headers={"User-Agent": "YmlManage-Check"}
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def kill_process(pid: int):
    """结束指定 PID 进程"""
    try:
        subprocess.run(
            f"taskkill /F /PID {pid}",
            shell=True,
            capture_output=True,
            encoding="gbk",
            errors="ignore"
        )
        time.sleep(0.5)
    except Exception:
        pass


def open_browser_when_ready(url: str, port: int, timeout: float = 8.0):
    """轮询等待后端服务端口就绪后，精准自动打开默认浏览器"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    time.sleep(0.3)
                    webbrowser.open(url)
                    return
        except Exception:
            pass
        time.sleep(0.3)
    # 若超时仍未探测成功，保底尝试直接唤起
    try:
        webbrowser.open(url)
    except Exception:
        pass


def handle_existing_port(port: int, local_url: str) -> bool:
    """
    检查端口占用：
    1. 若已有 YmlManage 在后台运行，直接唤起浏览器并友好提示
    2. 若被其他程序占用，提示或询问用户是否结束并接管端口
    返回 True 表示已由现有服务处理，无需启动新服务；返回 False 表示可继续正常启动
    """
    pid = get_pid_occupying_port(port)
    if not pid:
        return False

    if is_yml_manage_running(port):
        print("=" * 62)
        print("  ⚡ YmlManage 服务已在后台正常运行中！")
        print("=" * 62)
        print(f"  🌐 正在直接为您唤起浏览器: {local_url}")
        print("=" * 62)
        webbrowser.open(local_url)
        print(f"\n  💡 说明: 后台进程 PID 为 {pid}")
        print("  - 若需重新启动全新服务，请输入 [r] 并回车")
        print("  - 若无需重启，直接按回车或关闭本窗口即可继续在浏览器中使用\n")
        try:
            choice = input("请输入选择 (直接回车退出 / r 重启): ").strip().lower()
            if choice == "r":
                print(f">> 正在结束旧进程 (PID: {pid})...")
                kill_process(pid)
                return False
            return True
        except (KeyboardInterrupt, EOFError):
            return True
    else:
        print("=" * 62)
        print(f"  ⚠️ 端口 {port} 已被其他程序占用 (PID: {pid})")
        print("=" * 62)
        try:
            choice = input(f"是否尝试强制结束该进程 (PID: {pid}) 以便启动 YmlManage？[y/N]: ").strip().lower()
            if choice == "y":
                kill_process(pid)
                return False
            else:
                input("\n按回车键退出...")
                return True
        except (KeyboardInterrupt, EOFError):
            return True


def main():
    host = "0.0.0.0"
    port = 8080
    lan_ip = get_lan_ip()

    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://{lan_ip}:{port}"

    # 处理端口占用情况 (如已在后台运行则直接打开浏览器)
    if handle_existing_port(port, local_url):
        return

    print("=" * 62)
    print("  ⚡ YmlManage 节点母本维护管理平台")
    print("=" * 62)
    print(f"  🌐 本机电脑访问:  {local_url}")
    if lan_ip != "127.0.0.1":
        print(f"  📱 局域网设备访问: {lan_url}  (同 WiFi 下手机/平板/电脑)")
    print(f"  📂 母本配置存放:  {CURRENT_DIR / 'data' / 'profiles'}")
    print("=" * 62)
    print("  💡 提示: 若局域网设备无法打开，请检查 Windows 防火墙是否允许 Python 访问网络。")
    print("=" * 62 + "\n")

    # 启动后台守护线程，服务就绪后精准唤起浏览器
    threading.Thread(target=open_browser_when_ready, args=(local_url, port), daemon=True).start()

    try:
        import uvicorn
        uvicorn.run(
            "backend.app.main:app",
            host=host,
            port=port,
            reload=False,
            ws="none"
        )
    except KeyboardInterrupt:
        print("\n>> 用户已手动停止服务。")
    except BaseException as e:
        print("\n" + "!" * 62)
        print(f"❌ 服务启动发生异常: {e}")
        print("!" * 62)
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
