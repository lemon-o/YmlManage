import os
import re
import socket
import subprocess
import tempfile
import shutil
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import httpx
import ruamel.yaml

from .config import DEFAULT_TEST_URL

# Mihomo 官方核心路径
BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
MIHOMO_PATH = BIN_DIR / ("mihomo.exe" if os.name == "nt" else "mihomo")

# 常见机场公告、广告与非节点关键词
AD_KEYWORDS_REGEX = re.compile(
    r"(官网|文档|客户端|更新|电报|群|防失联|剩余|流量|到期|重置|通知|公告|发布页|地址|说明|测试|套餐|channel|t\.me|http)",
    re.IGNORECASE
)

# 常见虚假/占位 IP
FAKE_IPS = {"1.1.1.1", "2.2.2.2", "127.0.0.1", "0.0.0.0", "8.8.8.8", "8.8.4.4"}


def is_ad_or_fake_node(node: Dict[str, Any]) -> bool:
    """快速识别广告、非节点或占位虚假节点"""
    name = str(node.get("name", "")).strip()
    server = str(node.get("server", "")).strip().lower()

    if AD_KEYWORDS_REGEX.search(name):
        return True

    if server in FAKE_IPS:
        return True

    return False


def is_ip_address(val: str) -> bool:
    """判断字符串是否为标准 IPv4 格式"""
    v = str(val).strip()
    try:
        socket.inet_aton(v)
        return True
    except Exception:
        return False


async def resolve_domains_via_doh(domains: List[str]) -> Dict[str, str]:
    """
    通过国内公共 DoH (阿里 DNS / 腾讯 DNS HTTPS 端口 443) 解析节点真实公网 IP，
    彻底避开本地 Windows / 软路由 / 旁路由对 UDP 53 端口的 Fake-IP (198.18.x.x) 劫持。
    """
    hosts = {}
    unique_domains = list(set(d.strip() for d in domains if d and not is_ip_address(d)))
    if not unique_domains:
        return hosts

    async with httpx.AsyncClient(timeout=4.0) as client:
        async def resolve_one(domain: str):
            # 优先使用阿里云 DoH (HTTP/2 over TLS 443)
            try:
                res = await client.get(f"https://223.5.5.5/resolve?name={domain}&type=A")
                if res.status_code == 200:
                    ans = res.json().get("Answer", [])
                    ips = [a["data"] for a in ans if a.get("type") == 1]
                    if ips:
                        hosts[domain] = ips[0]
                        return
            except Exception:
                pass

            # 备用腾讯云 DoH
            try:
                res = await client.get(
                    "https://doh.pub/dns-query",
                    params={"name": domain, "type": "A"},
                    headers={"accept": "application/dns-json"}
                )
                if res.status_code == 200:
                    ans = res.json().get("Answer", [])
                    ips = [a["data"] for a in ans if a.get("type") == 1]
                    if ips:
                        hosts[domain] = ips[0]
            except Exception:
                pass

        await asyncio.gather(*(resolve_one(d) for d in unique_domains))
    return hosts


def find_free_port() -> int:
    """动态获取可用本地端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class MihomoSession:
    """
    管理 Mihomo 核心后台测试进程，支持：
    1. 快速并发延迟探测与死节点过滤 (测完延迟立即生成卡片)
    2. 保持会话供前端卡片逐一快速测速，按需切换 GLOBAL 代理
    3. 自动闲置超时释放资源
    """
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.temp_dir: Optional[str] = None
        self.ext_port: Optional[int] = None
        self.mixed_port: Optional[int] = None
        self.proxy_keys: List[str] = []
        self.node_mapping: Dict[str, Dict[str, Any]] = {}
        self.last_active: float = time.time()
        self._lock = asyncio.Lock()

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
        self.proxy_keys.clear()
        self.node_mapping.clear()

    async def start(self, nodes: List[Dict[str, Any]]) -> bool:
        async with self._lock:
            self.stop()
            if not MIHOMO_PATH.exists():
                return False

            self.ext_port = find_free_port()
            self.mixed_port = find_free_port()
            self.temp_dir = tempfile.mkdtemp(prefix="mihomo_session_")

            test_proxies = []
            self.node_mapping = {}
            self.proxy_keys = []

            for idx, n in enumerate(nodes):
                if is_ad_or_fake_node(n):
                    continue
                c = dict(n)
                node_key = f"P_{idx}_{c.get('type', 'node')}"
                c["name"] = node_key
                if not c.get("sni"):
                    c["sni"] = c.get("server")
                c["skip-cert-verify"] = True
                test_proxies.append(c)
                self.node_mapping[node_key] = n
                self.proxy_keys.append(node_key)

            if not test_proxies:
                return False

            # 通过公共 DoH 获取节点服务器的真实公网 IP，注入 hosts，免疫本地 Fake-IP 欺骗
            target_domains = [p.get("server") for p in test_proxies if p.get("server")]
            hosts_map = await resolve_domains_via_doh(target_domains)

            config = {
                "mixed-port": self.mixed_port,
                "external-controller": f"127.0.0.1:{self.ext_port}",
                "mode": "global",
                "log-level": "silent",
                "unified-delay": True,
                "tcp-concurrent": True,
                "hosts": hosts_map,
                "dns": {
                    "enable": True,
                    "ipv6": False,
                    "enhanced-mode": "redir-host",
                    "nameserver": [
                        "https://223.5.5.5/dns-query",
                        "https://doh.pub/dns-query"
                    ]
                },
                "proxies": test_proxies
            }

            config_path = os.path.join(self.temp_dir, "config.yaml")
            yaml = ruamel.yaml.YAML()
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f)

            self.proc = subprocess.Popen(
                [str(MIHOMO_PATH), "-f", config_path, "-d", self.temp_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # 等待核心就绪 (通常只需要 150-250ms)
            ready = False
            api_base = f"http://127.0.0.1:{self.ext_port}"
            for _ in range(35):
                await asyncio.sleep(0.08)
                try:
                    async with httpx.AsyncClient(timeout=0.3) as client:
                        r = await client.get(f"{api_base}/version")
                        if r.status_code == 200:
                            ready = True
                            break
                except Exception:
                    pass

            if not ready:
                self.stop()
                return False

            self.last_active = time.time()
            return True

    async def test_delays(
        self,
        test_url: str = DEFAULT_TEST_URL,
        timeout: float = 3.5,
        concurrency: int = 25,
        filter_dead: bool = True,
        on_progress: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        并发进行延迟检测，支持过滤死节点或保留标记为超时，支持实时进度回调
        """
        if not self.is_alive():
            return []

        self.last_active = time.time()
        api_base = f"http://127.0.0.1:{self.ext_port}"
        sem = asyncio.Semaphore(concurrency)
        timeout_ms = int(timeout * 1000)

        total_proxies = len(self.proxy_keys)
        completed_count = 0
        alive_count = 0

        async def check_delay(key: str):
            nonlocal completed_count, alive_count
            res_node = None
            async with sem:
                orig_node = self.node_mapping.get(key)
                if orig_node:
                    try:
                        async with httpx.AsyncClient(timeout=timeout + 1.2) as client:
                            res = await client.get(
                                f"{api_base}/proxies/{key}/delay",
                                params={"url": test_url, "timeout": timeout_ms}
                            )
                            if res.status_code == 200:
                                data = res.json()
                                d = data.get("delay", -1)
                                if d and d > 0:
                                    orig_node["delay"] = d
                                    orig_node["proxy_key"] = key
                                    res_node = orig_node
                    except Exception:
                        pass
                    if not res_node:
                        orig_node["delay"] = -1
                        orig_node["proxy_key"] = key
                        if not filter_dead:
                            res_node = orig_node

            completed_count += 1
            if res_node is not None and res_node.get("delay", -1) > 0:
                alive_count += 1

            if on_progress:
                try:
                    await on_progress(completed_count, total_proxies, alive_count)
                except Exception:
                    pass

            return res_node

        tasks = [check_delay(k) for k in self.proxy_keys]
        results = await asyncio.gather(*tasks)
        alive = [r for r in results if r is not None]
        # 存活节点按延迟升序排列，超时节点(-1)排在最后
        alive.sort(key=lambda x: (1 if x.get("delay", -1) <= 0 else 0, x.get("delay", 99999)))
        return alive


# 全局内核测试会话单例
session_manager = MihomoSession()


async def test_and_filter_nodes(
    nodes: List[Dict[str, Any]],
    test_url: str = DEFAULT_TEST_URL,
    concurrency: int = 25,
    timeout: float = 3.5,
    filter_dead: bool = True,
    on_progress: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    使用内置 Mihomo 官方内核执行真实延迟测试（Unified Delay 统一真实 RTT 延迟算法）。
    剔除本地至节点握手协议差异干扰，精确测量首字节真实响应时延 (TTFB / RTT)，支持死节点精准过滤。
    支持实时进度回调，测试完毕立即自动清理释放内核资源。
    """
    if not nodes:
        return []

    if MIHOMO_PATH.exists():
        started = await session_manager.start(nodes)
        if started:
            try:
                alive = await session_manager.test_delays(
                    test_url=test_url,
                    timeout=timeout,
                    concurrency=concurrency,
                    filter_dead=filter_dead,
                    on_progress=on_progress
                )
                return alive
            finally:
                session_manager.stop()

    # 回退备用：若无内核，标记为未测试
    alive = []
    for n in nodes:
        if not is_ad_or_fake_node(n):
            n["delay"] = -1
            alive.append(n)
    return alive


# 兼容别名
test_and_filter_nodes_session = test_and_filter_nodes


def stop_mihomo_session():
    """
    停止内核会话
    """
    session_manager.stop()
