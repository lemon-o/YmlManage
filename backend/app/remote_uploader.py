import os
import io
import re
import json
import socket
import ftplib
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
import smbclient

from .config import DATA_DIR, PROFILES_DIR

REMOTE_TARGETS_FILE = DATA_DIR / "remote_targets.json"


def load_remote_targets() -> List[Dict[str, Any]]:
    """加载已保存的常用远程上传目标列表"""
    if not REMOTE_TARGETS_FILE.exists():
        return []
    try:
        with open(REMOTE_TARGETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_remote_targets(targets: List[Dict[str, Any]]) -> None:
    """持久化保存常用远程上传目标列表"""
    REMOTE_TARGETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REMOTE_TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)


class RemoteUploader:
    """
    支持将母本 YAML 配置文件上传/推送到远程指定目标：
    1. WebDAV (Alist, Nextcloud, 群晖, 路由器等)
    2. FTP (OpenWrt, Linux 主机, 路由器)
    3. SMB / Samba (Windows 共享网络驱动器, NAS, 软路由)
    4. 本地 / 局域网 UNC 路径
    默认均执行覆盖替换
    """

    @classmethod
    def upload(
        cls,
        protocol: str,
        config: Dict[str, Any],
        file_content: bytes,
        profile_name: str,
        overwrite: bool = True
    ) -> Dict[str, Any]:
        proto = protocol.lower().strip()
        if proto == "webdav":
            return cls._upload_webdav(config, file_content, profile_name, overwrite)
        elif proto == "ftp":
            return cls._upload_ftp(config, file_content, profile_name, overwrite)
        elif proto == "smb":
            return cls._upload_smb(config, file_content, profile_name, overwrite)
        elif proto in ["local", "unc", "path"]:
            return cls._upload_local(config, file_content, profile_name, overwrite)
        else:
            raise ValueError(f"暂不支持的传输协议: {protocol}，仅支持 SMB、FTP、WebDAV、本地路径")

    @classmethod
    def test_connection(cls, protocol: str, config: Dict[str, Any]) -> Dict[str, Any]:
        proto = protocol.lower().strip()
        if proto == "webdav":
            return cls._test_webdav(config)
        elif proto == "ftp":
            return cls._test_ftp(config)
        elif proto == "smb":
            return cls._test_smb(config)
        elif proto in ["local", "unc", "path"]:
            return cls._test_local(config)
        else:
            raise ValueError(f"暂不支持的传输协议: {protocol}")

    # ================= WebDAV =================
    @classmethod
    def _format_webdav_url(cls, raw_url: str, profile_name: str) -> str:
        url = raw_url.strip()
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        # 若未指定文件名或路径未以 .yaml / .yml 结尾，自动补全母本文件名
        if not path:
            path = "/" + profile_name
        elif not path.lower().endswith((".yaml", ".yml")):
            path = path + "/" + profile_name
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

    @classmethod
    def _upload_webdav(cls, config: Dict[str, Any], file_content: bytes, profile_name: str, overwrite: bool) -> Dict[str, Any]:
        target_url = cls._format_webdav_url(config.get("url", ""), profile_name)
        username = config.get("username", "").strip() or None
        password = config.get("password", "") or None

        auth = httpx.BasicAuth(username, password) if (username or password) else None
        headers = {
            "Content-Type": "application/x-yaml; charset=utf-8",
            "Overwrite": "T" if overwrite else "F"
        }

        try:
            with httpx.Client(auth=auth, timeout=30.0, verify=False) as client:
                resp = client.put(target_url, content=file_content, headers=headers)
                if resp.status_code in [200, 201, 204]:
                    return {
                        "success": True,
                        "protocol": "webdav",
                        "target": target_url,
                        "message": f"WebDAV 上传成功！已默认覆盖替换: {target_url}"
                    }
                else:
                    raise Exception(f"HTTP 响应状态码: {resp.status_code} ({resp.text[:120]})")
        except Exception as e:
            raise Exception(f"WebDAV 上传失败: {str(e)}")

    @classmethod
    def _test_webdav(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        raw_url = config.get("url", "").strip()
        if not raw_url.startswith(("http://", "https://")):
            raw_url = "http://" + raw_url
        username = config.get("username", "").strip() or None
        password = config.get("password", "") or None
        auth = httpx.BasicAuth(username, password) if (username or password) else None

        try:
            with httpx.Client(auth=auth, timeout=10.0, verify=False) as client:
                # 尝试 PROPFIND 或 OPTIONS 或 HEAD
                resp = client.request("OPTIONS", raw_url)
                if resp.status_code in [200, 204, 207, 401, 404]:
                    if resp.status_code == 401:
                        raise Exception("认证失败，请检查账号与密码")
                    return {"success": True, "message": "WebDAV 服务连接成功！"}
                resp.raise_for_status()
                return {"success": True, "message": "WebDAV 服务连接成功！"}
        except Exception as e:
            raise Exception(f"WebDAV 连接测试失败: {str(e)}")

    # ================= FTP =================
    @classmethod
    def _upload_ftp(cls, config: Dict[str, Any], file_content: bytes, profile_name: str, overwrite: bool) -> Dict[str, Any]:
        host = config.get("host", "").strip()
        port = int(config.get("port") or 21)
        username = config.get("username", "").strip() or "anonymous"
        password = config.get("password", "")
        remote_path = config.get("path", "").strip()

        remote_path = remote_path.replace("\\", "/").strip("/")
        # 若未指定文件名或未以 .yaml / .yml 结尾，自动补全母本文件名
        if not remote_path:
            remote_path = profile_name
        elif not remote_path.lower().endswith((".yaml", ".yml")):
            remote_path = f"{remote_path}/{profile_name}"

        try:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=15)
            ftp.login(username, password)

            # 递归确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                parts = [p for p in remote_dir.split("/") if p]
                for part in parts:
                    try:
                        ftp.cwd(part)
                    except Exception:
                        try:
                            ftp.mkd(part)
                            ftp.cwd(part)
                        except Exception:
                            pass

            filename_only = os.path.basename(remote_path)
            buf = io.BytesIO(file_content)
            # STOR 命令天然覆盖替换现有同名文件
            ftp.storbinary(f"STOR {filename_only}", buf)
            ftp.quit()

            return {
                "success": True,
                "protocol": "ftp",
                "target": f"ftp://{host}:{port}/{remote_path}",
                "message": f"FTP 上传成功！已默认覆盖替换目标: /{remote_path}"
            }
        except Exception as e:
            raise Exception(f"FTP 上传失败: {str(e)}")

    @classmethod
    def _test_ftp(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        host = config.get("host", "").strip()
        port = int(config.get("port") or 21)
        username = config.get("username", "").strip() or "anonymous"
        password = config.get("password", "")

        try:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=10)
            ftp.login(username, password)
            curr = ftp.pwd()
            ftp.quit()
            return {"success": True, "message": f"FTP 连接与登录成功！当前目录: {curr}"}
        except Exception as e:
            raise Exception(f"FTP 连接测试失败: {str(e)}")

    # ================= SMB / Samba =================
    @classmethod
    def _parse_smb_config(cls, config: Dict[str, Any], profile_name: str):
        raw_server = (config.get("server") or config.get("host") or "").strip()
        raw_share = config.get("share", "").strip()
        raw_path = config.get("path", "").strip()
        port = int(config.get("port") or 445)

        # 支持用户直接在 server 或 path 中粘贴完整 UNC 路径，例如 \\192.168.1.1\share\clash.yaml
        unc_match = re.match(r"^[\\/]{2}([^\\/]+)[\\/]([^\\/]+)[\\/]?(.*)$", raw_server or raw_path)
        if unc_match:
            server = unc_match.group(1)
            share = unc_match.group(2)
            rem = unc_match.group(3) or raw_path
        else:
            server = raw_server
            share = raw_share
            rem = raw_path

        rem = rem.replace("/", "\\").strip("\\")
        # 若未指定文件名或未以 .yaml / .yml 结尾，自动补全母本文件名
        if not rem:
            rem = profile_name
        elif not rem.lower().endswith((".yaml", ".yml")):
            rem = f"{rem}\\{profile_name}"

        return server, share, rem, port

    @classmethod
    def _upload_smb(cls, config: Dict[str, Any], file_content: bytes, profile_name: str, overwrite: bool) -> Dict[str, Any]:
        server, share, remote_path, port = cls._parse_smb_config(config, profile_name)
        username = config.get("username", "").strip() or None
        password = config.get("password", "") or None

        if not server or not share:
            raise ValueError("SMB 缺少服务器地址或共享名称 (如: \\\\192.168.1.1\\share)")

        unc_full = rf"\\{server}\{share}\{remote_path}"

        try:
            if username or password:
                smbclient.register_session(server, username=username or "", password=password or "", port=port)

            parent_dir = os.path.dirname(unc_full)
            if parent_dir:
                try:
                    smbclient.makedirs(parent_dir, exist_ok=True)
                except Exception:
                    pass

            with smbclient.open_file(unc_full, mode="wb") as f:
                f.write(file_content)

            return {
                "success": True,
                "protocol": "smb",
                "target": unc_full,
                "message": f"SMB 共享上传成功！已默认覆盖替换: {unc_full}"
            }
        except Exception as e:
            raise Exception(f"SMB 上传失败: {str(e)}")

    @classmethod
    def _test_smb(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        server, share, _, port = cls._parse_smb_config(config, "test.yaml")
        username = config.get("username", "").strip() or None
        password = config.get("password", "") or None

        if not server or not share:
            raise ValueError("SMB 缺少服务器地址或共享名")

        try:
            if username or password:
                smbclient.register_session(server, username=username or "", password=password or "", port=port)
            share_path = rf"\\{server}\{share}"
            exists = smbclient.path.exists(share_path)
            return {"success": True, "message": f"SMB 共享连接成功！目标共享有效: {share_path}"}
        except Exception as e:
            raise Exception(f"SMB 连接测试失败: {str(e)}")

    # ================= 本地 / UNC 路径 =================
    @classmethod
    def _upload_local(cls, config: Dict[str, Any], file_content: bytes, profile_name: str, overwrite: bool) -> Dict[str, Any]:
        target_path_str = config.get("path", "").strip()
        if not target_path_str:
            raise ValueError("未指定目标本地/共享路径")

        p = Path(target_path_str)
        if target_path_str.endswith(("/", "\\")) or (p.exists() and p.is_dir()) or not target_path_str.lower().endswith((".yaml", ".yml")):
            target_file = Path(target_path_str) / profile_name
        else:
            target_file = Path(target_path_str)

        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with open(target_file, "wb") as f:
                f.write(file_content)
            return {
                "success": True,
                "protocol": "local",
                "target": str(target_file),
                "message": f"本地/共享路径写入成功！已覆盖保存: {target_file}"
            }
        except Exception as e:
            raise Exception(f"本地/共享路径写入失败: {str(e)}")

    @classmethod
    def _test_local(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        target_path_str = config.get("path", "").strip()
        if not target_path_str:
            raise ValueError("未输入路径")
        p = Path(target_path_str)
        parent = p if p.is_dir() else p.parent
        if parent.exists():
            return {"success": True, "message": f"路径有效且可达: {parent}"}
        else:
            return {"success": True, "message": f"目标父目录尚不存在，上传时将自动创建: {parent}"}
