import os
import sys
import time
import socket
import threading
import webbrowser
import uvicorn
from pathlib import Path

# 设置控制台 utf-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
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


def open_browser_delayed(url: str, delay: float = 1.0):
    """延迟等待服务启动后自动打开本机默认浏览器"""
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    host = "0.0.0.0"  # 监听 0.0.0.0 允许局域网内所有设备访问
    port = 8080
    lan_ip = get_lan_ip()

    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://{lan_ip}:{port}"

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

    # 本机后台线程自动打开浏览器
    threading.Thread(target=open_browser_delayed, args=(local_url, 1.2), daemon=True).start()

    try:
        # ws='none' 避免受系统全局老版本 websockets 库版本冲突影响
        uvicorn.run(
            "backend.app.main:app",
            host=host,
            port=port,
            reload=False,
            ws="none"
        )
    except Exception as e:
        print("\n" + "!" * 62)
        print(f"❌ 服务启动发生异常: {e}")
        print("!" * 62)
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
