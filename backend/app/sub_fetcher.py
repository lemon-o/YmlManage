import re
import json
import base64
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from ruamel.yaml import YAML

from .config import DEFAULT_USER_AGENT


def safe_base64_decode(s: str) -> str:
    """安全 Base64 解码（自动补齐 padding，兼容 URL-safe）"""
    s = s.strip()
    # 替换 urlsafe 字符
    s = s.replace("-", "+").replace("_", "/")
    # 补齐等号
    missing_padding = len(s) % 4
    if missing_padding != 0:
        s += "=" * (4 - missing_padding)
    try:
        return base64.b64decode(s).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_ss_link(url: str) -> Optional[Dict[str, Any]]:
    """解析 ss:// 链接为 Clash 节点字典"""
    try:
        # ss://base64(#name) 或 ss://base64@server:port(#name)
        parsed = urllib.parse.urlparse(url)
        name = urllib.parse.unquote(parsed.fragment) or "Shadowsocks"
        
        main_part = url[5:].split("#")[0]
        if "@" in main_part:
            userinfo, hostport = main_part.split("@", 1)
            # userinfo 可能是 base64
            decoded_user = safe_base64_decode(userinfo) or userinfo
            if ":" in decoded_user:
                cipher, password = decoded_user.split(":", 1)
            else:
                return None
            host, port_str = hostport.split(":", 1)
            port = int(port_str.split("/")[0].split("?")[0])
        else:
            decoded = safe_base64_decode(main_part)
            if "@" in decoded:
                userinfo, hostport = decoded.split("@", 1)
                cipher, password = userinfo.split(":", 1)
                host, port_str = hostport.split(":", 1)
                port = int(port_str.split("/")[0].split("?")[0])
            else:
                return None

        return {
            "name": name,
            "type": "ss",
            "server": host,
            "port": port,
            "cipher": cipher,
            "password": password
        }
    except Exception:
        return None


def parse_vmess_link(url: str) -> Optional[Dict[str, Any]]:
    """解析 vmess:// 链接为 Clash 节点字典"""
    try:
        raw_b64 = url[8:].strip()
        decoded = safe_base64_decode(raw_b64)
        if not decoded:
            return None
        data = json.loads(decoded)
        name = data.get("ps", "VMess")
        server = data.get("add", "")
        port = int(data.get("port", 443))
        uuid = data.get("id", "")
        alter_id = int(data.get("aid", 0))
        net = data.get("net", "tcp")
        tls = (data.get("tls", "") == "tls")

        node: Dict[str, Any] = {
            "name": name,
            "type": "vmess",
            "server": server,
            "port": port,
            "uuid": uuid,
            "alterId": alter_id,
            "cipher": data.get("scy", "auto"),
            "udp": True,
            "tls": tls
        }
        if net == "ws":
            node["network"] = "ws"
            node["ws-opts"] = {
                "path": data.get("path", "/"),
                "headers": {"Host": data.get("host", server)}
            }
        elif net in ["grpc", "h2"]:
            node["network"] = net

        if data.get("sni"):
            node["servername"] = data.get("sni")

        return node
    except Exception:
        return None


def parse_vless_link(url: str) -> Optional[Dict[str, Any]]:
    """解析 vless:// 链接 (含 Reality) 为 Clash/Mihomo 节点字典"""
    try:
        parsed = urllib.parse.urlparse(url)
        name = urllib.parse.unquote(parsed.fragment) or "VLESS"
        uuid = parsed.username
        server = parsed.hostname
        port = parsed.port or 443
        params = urllib.parse.parse_qs(parsed.query)

        security = params.get("security", ["none"])[0]
        flow = params.get("flow", [""])[0]
        net = params.get("type", ["tcp"])[0]
        sni = params.get("sni", [""])[0]

        node: Dict[str, Any] = {
            "name": name,
            "type": "vless",
            "server": server,
            "port": port,
            "uuid": uuid,
            "udp": True,
            "tls": security in ["tls", "reality"]
        }
        if flow:
            node["flow"] = flow
        if sni:
            node["servername"] = sni

        if security == "reality":
            pbk = params.get("pbk", [""])[0]
            sid = params.get("sid", [""])[0]
            node["reality-opts"] = {
                "public-key": pbk,
                "short-id": sid
            }
            if params.get("fp"):
                node["client-fingerprint"] = params.get("fp")[0]

        if net == "ws":
            node["network"] = "ws"
            path = params.get("path", ["/"])[0]
            host = params.get("host", [""])[0] or server
            node["ws-opts"] = {"path": path, "headers": {"Host": host}}
        elif net == "grpc":
            node["network"] = "grpc"
            service_name = params.get("serviceName", [""])[0]
            node["grpc-opts"] = {"grpc-service-name": service_name}

        return node
    except Exception:
        return None


def parse_trojan_link(url: str) -> Optional[Dict[str, Any]]:
    """解析 trojan:// 链接为 Clash 节点字典"""
    try:
        parsed = urllib.parse.urlparse(url)
        name = urllib.parse.unquote(parsed.fragment) or "Trojan"
        password = parsed.username
        server = parsed.hostname
        port = parsed.port or 443
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get("sni", [""])[0]

        node: Dict[str, Any] = {
            "name": name,
            "type": "trojan",
            "server": server,
            "port": port,
            "password": password,
            "udp": True,
            "sni": sni or server
        }
        return node
    except Exception:
        return None


def parse_hysteria2_link(url: str) -> Optional[Dict[str, Any]]:
    """解析 hysteria2:// 或 hy2:// 链接为 Mihomo 节点字典"""
    try:
        parsed = urllib.parse.urlparse(url)
        name = urllib.parse.unquote(parsed.fragment) or "Hysteria2"
        password = parsed.username
        server = parsed.hostname
        port = parsed.port or 443
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get("sni", [""])[0]

        node: Dict[str, Any] = {
            "name": name,
            "type": "hysteria2",
            "server": server,
            "port": port,
            "password": password,
            "sni": sni or server
        }
        return node
    except Exception:
        return None


def parse_node_uri(line: str) -> Optional[Dict[str, Any]]:
    """根据协议前缀分流解析单节点链接"""
    line = line.strip()
    if not line:
        return None
    if line.startswith("vmess://"):
        return parse_vmess_link(line)
    elif line.startswith("vless://"):
        return parse_vless_link(line)
    elif line.startswith("ss://"):
        return parse_ss_link(line)
    elif line.startswith("trojan://"):
        return parse_trojan_link(line)
    elif line.startswith("hysteria2://") or line.startswith("hy2://"):
        return parse_hysteria2_link(line)
    return None


class SubscriptionFetcher:
    """拉取并解析外部订阅中的节点"""

    @classmethod
    async def fetch_and_parse(cls, url: str, custom_ua: Optional[str] = None) -> List[Dict[str, Any]]:
        ua = custom_ua or DEFAULT_USER_AGENT
        headers = {
            "User-Agent": ua,
            "Accept": "*/*"
        }

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, verify=False) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                content = resp.text
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 403:
                raise ValueError(
                    "订阅源服务器拒绝访问 (HTTP 403 Forbidden)。\n"
                    "常见原因：\n"
                    "1. 该订阅链接已过期、流量已用尽，或在机场后台重置了订阅 Token（导致旧链接失效）；\n"
                    "2. 机场已更换订阅域名（机场被封后常更换订阅地址，请登录机场官网复制最新生成的订阅链接）；\n"
                    "3. 机场订阅开启了防刷限制或禁止当前 IP / 地区直接访问。"
                ) from e
            elif status == 404:
                raise ValueError("订阅链接不存在 (HTTP 404 Not Found)，请核对链接地址是否正确或已被机场下线。") from e
            elif status == 401:
                raise ValueError("订阅认证失败 (HTTP 401 Unauthorized)，Token 鉴权失败，请重新获取最新链接。") from e
            elif status in [502, 503, 504]:
                raise ValueError(f"订阅服务器暂时不可用 (HTTP {status})，机场服务器可能正在维护，请稍后重试。") from e
            else:
                raise ValueError(f"订阅服务器返回错误状态码 (HTTP {status})") from e
        except httpx.ConnectTimeout:
            raise ValueError("连接订阅服务器超时，该订阅域名可能无法直连，请检查网络。")
        except httpx.ConnectError as e:
            raise ValueError(f"无法连接到订阅服务器 ({str(e)})，请检查域名解析或网络连通性。")
        except Exception as e:
            raise ValueError(f"拉取订阅发生异常: {str(e)}") from e

        return cls.parse_content(content)

    @classmethod
    def parse_content(cls, content: str) -> List[Dict[str, Any]]:
        """智能解析订阅内容（优先尝试 Clash YAML，其次尝试 Base64 / 纯节点链接列表）"""
        content = content.strip()
        if not content:
            return []

        # 1. 尝试作为 YAML 解析 (Clash 格式)
        if "proxies:" in content or ("port:" in content and "rules:" in content):
            try:
                yaml = YAML(typ="safe")
                data = yaml.load(content)
                if isinstance(data, dict) and "proxies" in data:
                    proxies = data["proxies"]
                    if isinstance(proxies, list):
                        valid_nodes = []
                        for p in proxies:
                            if isinstance(p, dict) and "name" in p and "server" in p:
                                valid_nodes.append(p)
                        if valid_nodes:
                            return valid_nodes
            except Exception:
                pass

        # 2. 尝试 Base64 解码后按行解析
        decoded_text = safe_base64_decode(content)
        parse_target = decoded_text if decoded_text and any(
            x in decoded_text for x in ["vmess://", "vless://", "ss://", "trojan://", "hy2://", "hysteria2://"]
        ) else content

        # 3. 按行解析单节点链接
        nodes = []
        for line in parse_target.splitlines():
            line = line.strip()
            if not line:
                continue
            parsed_node = parse_node_uri(line)
            if parsed_node:
                nodes.append(parsed_node)

        # 4. 如果仍未解析出来，再尝试宽松 YAML 扫描
        if not nodes:
            try:
                yaml = YAML(typ="safe")
                data = yaml.load(content)
                if isinstance(data, dict) and "proxies" in data and isinstance(data["proxies"], list):
                    return [p for p in data["proxies"] if isinstance(p, dict) and "name" in p]
            except Exception:
                pass

        return nodes
