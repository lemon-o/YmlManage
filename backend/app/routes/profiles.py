import os
import re
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
import httpx
from ruamel.yaml import YAML

from ..config import (
    PROFILES_DIR,
    ROOT_TEMPLATE_FILE,
    DEFAULT_USER_AGENT,
    DEFAULT_TEST_URL,
    DOMESTIC_TEST_URLS
)
from ..yaml_manager import YamlManager
from ..sub_fetcher import parse_node_uri

router = APIRouter(prefix="/api/profiles", tags=["Profiles"])


class DownloadProfileRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="母本名称 (可选，若不填则自动识别文件名)")
    url: str = Field(..., description="母本订阅链接")
    user_agent: Optional[str] = Field(default=None, description="自定义 User-Agent")


class SaveRawRequest(BaseModel):
    content: str = Field(..., description="YAML 文本内容")


class SaveStructureRequest(BaseModel):
    proxies: List[Dict[str, Any]] = Field(default_factory=list, description="节点列表")
    proxy_groups: List[Dict[str, Any]] = Field(default_factory=list, description="策略组列表")
    rules: Optional[List[str]] = Field(default=None, description="分流规则列表")


class ParseNodeRequest(BaseModel):
    link: str = Field(..., description="节点单链接如 vless://, hysteria2://, vmess://")


class RestoreBackupRequest(BaseModel):
    backup_filename: str = Field(..., description="备份文件名")


class UpdateTestUrlRequest(BaseModel):
    test_url: str = Field(default=DEFAULT_TEST_URL, description="测速与测延迟接口 URL")


FALLBACK_TEMPLATE = f"""# Clash / Mihomo 母本配置文件
port: 7890
socks-port: 7891
mixed-port: 7890
allow-lan: true
mode: Rule
log-level: info
unified-delay: true
tcp-concurrent: true
external-controller: 127.0.0.1:9090

dns:
  enable: true
  listen: 0.0.0.0:1053
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - 223.5.5.5
    - 119.29.29.29
    - https://dns.alidns.com/dns-query

# 节点列表
proxies: []

# 策略组列表
proxy-groups:
  - name: 节点选择
    type: select
    proxies:
      - 自动选择
      - DIRECT

  - name: 自动选择
    type: url-test
    url: {DEFAULT_TEST_URL}
    interval: 300
    tolerance: 50
    proxies: []

  - name: 香港节点
    type: select
    proxies: []

  - name: 日本节点
    type: select
    proxies: []

  - name: 美国节点
    type: select
    proxies: []

  - name: 狮城节点
    type: select
    proxies: []

  - name: 漏网之鱼
    type: select
    proxies:
      - 节点选择
      - DIRECT

# 分流规则
rules:
  - DOMAIN-SUFFIX,local,DIRECT
  - IP-CIDR,127.0.0.0/8,DIRECT
  - IP-CIDR,192.168.0.0/16,DIRECT
  - MATCH,漏网之鱼
"""


def get_default_template_content() -> str:
    """优先使用根目录【母本模板.yml】，若不存在则使用回退模板"""
    if ROOT_TEMPLATE_FILE.exists():
        with open(ROOT_TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return FALLBACK_TEMPLATE


def clean_filename(name: str) -> str:
    """清理并规范化文件名（自动多重 URL 解码，支持中文与特殊字符）"""
    decoded = name.strip()
    for _ in range(3):
        unquoted = urllib.parse.unquote(decoded)
        if unquoted == decoded:
            break
        decoded = unquoted
    clean = re.sub(r'[\\/*?:"<>|]', "", decoded.strip())
    if not clean:
        clean = "master"
    if not clean.endswith((".yaml", ".yml")):
        clean += ".yaml"
    return clean


@router.get("/test-urls")
def get_available_test_urls():
    """获取推荐的国内直连与备用测速接口列表"""
    return {
        "default_url": DEFAULT_TEST_URL,
        "list": DOMESTIC_TEST_URLS
    }


@router.post("/{name}/update-test-url")
def update_profile_test_url(name: str, req: UpdateTestUrlRequest):
    """一键更新指定母本所有 url-test 策略组的测速与测延迟接口为国内直连接口"""
    try:
        res = YamlManager.update_profile_test_urls(name, req.test_url)
        return res
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="母本不存在")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新测速接口失败: {str(e)}")


@router.get("")
def list_profiles():
    """获取所有母本文件列表"""
    return YamlManager.list_profiles()


def get_lan_ip() -> str:
    """获取本机在局域网中的 IPv4 地址"""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('223.5.5.5', 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


@router.get("/system-info")
def get_system_info():
    """获取本机局域网 IP 与访问地址，供局域网内其他设备访问"""
    lan_ip = get_lan_ip()
    port = 8080
    return {
        "lan_ip": lan_ip,
        "port": port,
        "lan_url": f"http://{lan_ip}:{port}",
        "local_url": f"http://127.0.0.1:{port}"
    }


@router.get("/{name}")
def get_profile_detail(name: str):
    """获取指定母本的摘要信息"""
    summary = YamlManager.get_profile_summary(name)
    if summary.get("proxy_count") == 0 and summary.get("group_count") == 0 and "error" in summary:
        raise HTTPException(status_code=404, detail=f"母本不存在或解析失败: {summary.get('error')}")
    # 同时返回嵌套 summary，确保向前向后双向兼容
    summary["summary"] = {
        "groups": summary.get("groups", []),
        "proxy_count": summary.get("proxy_count", 0),
        "group_count": summary.get("group_count", 0),
        "test_url": summary.get("test_url", DEFAULT_TEST_URL)
    }
    return summary


import urllib.parse
from datetime import datetime


def detect_filename_from_url_and_headers(url: str, headers: Any) -> str:
    """自动从响应头或 URL 地址中智能提取 YAML 文件名"""
    # 1. 优先检查 Content-Disposition 响应头
    cd = headers.get("content-disposition", "") if headers else ""
    if cd:
        m_utf8 = re.search(r"filename\*=UTF-8''([^;\r\n]+)", cd, re.IGNORECASE)
        if m_utf8:
            fname = m_utf8.group(1).strip("\"' ")
            if fname:
                return clean_filename(fname)
        m = re.search(r'filename="?([^";\r\n]+)"?', cd, re.IGNORECASE)
        if m:
            fname = m.group(1).strip("\"' ")
            if fname:
                return clean_filename(fname)

    # 2. 检查 URL 路径后缀 (先提取文件名并进行 URL 解码)
    try:
        parsed = urllib.parse.urlparse(url)
        path_name = Path(parsed.path).name
        if path_name:
            unquoted_name = urllib.parse.unquote(path_name)
            if unquoted_name.lower().endswith((".yaml", ".yml")):
                return clean_filename(unquoted_name)
    except Exception:
        pass

    # 3. 检查 URL query 参数中可能包含的文件名
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        for q_key in ["file", "filename", "name", "path"]:
            if q_key in query_params and query_params[q_key]:
                q_val = query_params[q_key][0]
                q_name = Path(urllib.parse.unquote(q_val)).name
                if q_name and q_name.lower().endswith((".yaml", ".yml")):
                    return clean_filename(q_name)
    except Exception:
        pass

    # 4. 检查域名主机名
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.split(":")[0]
        if host and host not in ["127.0.0.1", "localhost"]:
            parts = [p for p in host.split(".") if p not in ["sub", "api", "www", "client"]]
            clean_host = "_".join(parts) if parts else host
            clean_host = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fa5]", "_", clean_host)
            if clean_host:
                return f"{clean_host}.yaml"
    except Exception:
        pass

    # 5. 回退使用时间戳命名
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"sub_profile_{ts}.yaml"


@router.post("/download")
async def download_profile_from_url(req: DownloadProfileRequest):
    """直接输入订阅 URL 自动下载并保存为母本（无需手动输入名称，自动读取识别）"""
    ua = req.user_agent or DEFAULT_USER_AGENT
    headers = {
        "User-Agent": ua,
        "Accept": "*/*"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25.0, verify=False) as client:
            resp = await client.get(req.url, headers=headers)
            resp.raise_for_status()
            content = resp.text
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 403:
            raise HTTPException(
                status_code=400,
                detail="订阅服务器拒绝访问 (HTTP 403 Forbidden)。常见原因：订阅已过期、Token 已在机场后台重置，或机场已更换订阅域名，请登录机场官网复制最新链接。"
            )
        elif status == 404:
            raise HTTPException(status_code=400, detail="订阅链接不存在 (HTTP 404 Not Found)，请核对订阅地址。")
        elif status == 401:
            raise HTTPException(status_code=400, detail="订阅认证失败 (HTTP 401 Unauthorized)，Token 鉴权失效。")
        else:
            raise HTTPException(status_code=400, detail=f"订阅服务器返回错误状态码 (HTTP {status})")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"拉取订阅链接失败: {str(e)}")

    # 自动识别文件名
    if req.name and req.name.strip():
        filename = clean_filename(req.name.strip())
    else:
        filename = detect_filename_from_url_and_headers(req.url, resp.headers)

    # 避免与内置母本模板同名
    if filename in ["母本模板.yaml", "母本模板.yml"]:
        filename = f"已下载_{filename}"

    save_path = PROFILES_DIR / filename

    # 验证是否为合法 YAML
    try:
        yaml = YAML(typ="safe")
        data = yaml.load(content)
        if not isinstance(data, dict):
            raise ValueError("下载的内容不是有效的 YAML 字典对象")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载的内容非合规 YAML 配置文件: {str(e)}")

    # 将外部默认的 gstatic 测速地址自动优化为国内直连测速接口
    if "gstatic.com/generate_204" in content:
        content = content.replace("http://www.gstatic.com/generate_204", DEFAULT_TEST_URL)
        content = content.replace("https://www.gstatic.com/generate_204", DEFAULT_TEST_URL)

    # 保存文件（若已存在先自动备份）
    if save_path.exists():
        YamlManager.create_backup(filename)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "success": True,
        "filename": filename,
        "message": f"成功下载并保存母本: {filename}",
        "summary": YamlManager.get_profile_summary(filename)
    }


@router.post("/upload")
async def upload_profile_file(file: UploadFile = File(...), name: Optional[str] = Form(None)):
    """上传本地 YAML 文件保存为母本"""
    fname = name if name else file.filename
    filename = clean_filename(fname)
    save_path = PROFILES_DIR / filename

    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("gbk", errors="ignore")

    try:
        yaml = YAML(typ="safe")
        data = yaml.load(content)
        if not isinstance(data, dict):
            raise ValueError("上传内容不是有效的 YAML 字典对象")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件不是有效的 YAML: {str(e)}")

    # 将 gstatic 测速地址自动优化为国内直连接口
    if "gstatic.com/generate_204" in content:
        content = content.replace("http://www.gstatic.com/generate_204", DEFAULT_TEST_URL)
        content = content.replace("https://www.gstatic.com/generate_204", DEFAULT_TEST_URL)

    if save_path.exists():
        YamlManager.create_backup(filename)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "success": True,
        "filename": filename,
        "message": f"成功上传母本: {filename}"
    }


@router.post("/create-default")
def create_default_profile(name: Optional[str] = "母本模板"):
    """基于根目录【母本模板.yml】创建母本"""
    filename = clean_filename(name)
    save_path = PROFILES_DIR / filename

    if save_path.exists():
        raise HTTPException(status_code=400, detail=f"文件 {filename} 已存在")

    template_content = get_default_template_content()
    # 确保模板内容使用国内直连接口
    if "gstatic.com/generate_204" in template_content:
        template_content = template_content.replace("http://www.gstatic.com/generate_204", DEFAULT_TEST_URL)
        template_content = template_content.replace("https://www.gstatic.com/generate_204", DEFAULT_TEST_URL)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(template_content)

    return {
        "success": True,
        "filename": filename,
        "message": f"成功创建母本: {filename}"
    }


@router.delete("/{name}")
def delete_profile(name: str):
    """删除指定的母本"""
    success = YamlManager.delete_profile(name)
    if not success:
        raise HTTPException(status_code=404, detail="母本文件不存在")
    return {"success": True, "message": f"成功删除母本 {name}"}


@router.get("/{name}/raw")
def get_raw_content(name: str):
    """获取母本原始 YAML 文本"""
    try:
        content = YamlManager.get_raw_yaml(name)
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="母本不存在")


@router.put("/{name}/raw")
def save_raw_content(name: str, req: SaveRawRequest):
    """在线保存并校验原始 YAML 文本"""
    try:
        YamlManager.save_raw_yaml(name, req.content)
        return {"success": True, "message": "保存成功，已自动备份旧版本"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"保存失败，YAML 语法可能有误: {str(e)}")


@router.get("/{name}/structure")
def get_profile_structure(name: str):
    """获取母本完整结构（节点列表与策略组列表），供可视化编辑使用"""
    try:
        return YamlManager.get_profile_structure(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="母本不存在")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析母本结构失败: {str(e)}")


@router.put("/{name}/structure")
def save_profile_structure(name: str, req: SaveStructureRequest):
    """可视化保存母本中的节点与策略组，无损写回并自动备份"""
    try:
        return YamlManager.save_profile_structure(name, req.proxies, req.proxy_groups, req.rules)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="母本不存在")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"保存母本结构失败: {str(e)}")


@router.post("/{name}/preview-yaml")
def preview_profile_yaml(name: str, req: SaveStructureRequest):
    """根据当前修改的节点和策略组生成实时 YAML 预览文本（不保存至磁盘）"""
    try:
        yaml_str = YamlManager.preview_profile_yaml(name, req.proxies, req.proxy_groups, req.rules)
        return {"yaml": yaml_str}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"生成 YAML 预览失败: {str(e)}")


@router.post("/parse-yaml")
def parse_yaml_text(req: SaveRawRequest):
    """解析任意 YAML 文本中的节点和策略组"""
    try:
        return YamlManager.parse_yaml_to_structure(req.content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"YAML 解析失败: {str(e)}")


@router.post("/parse-node")
def parse_node(req: ParseNodeRequest):
    """解析单个节点链接 (vless, vmess, hysteria2, ss, trojan) 为 Clash 节点字典"""
    node = parse_node_uri(req.link.strip())
    if not node:
        raise HTTPException(status_code=400, detail="无法解析此节点链接，可能链接格式不受支持")
    return {"node": node}


@router.get("/{name}/backups")
def get_profile_backups(name: str):
    """获取某母本的所有历史备份"""
    return YamlManager.list_backups(name)


@router.post("/{name}/restore")
def restore_profile_backup(name: str, req: RestoreBackupRequest):
    """从指定备份还原母本"""
    try:
        YamlManager.restore_backup(name, req.backup_filename)
        return {"success": True, "message": f"成功还原至备份 {req.backup_filename}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"恢复失败: {str(e)}")


@router.delete("/{name}/backups/{backup_filename}")
def delete_profile_backup(name: str, backup_filename: str):
    """删除指定的快照备份文件"""
    try:
        YamlManager.delete_backup(name, backup_filename)
        return {"success": True, "message": f"成功删除快照备份 {backup_filename}"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="快照备份文件不存在")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"删除快照失败: {str(e)}")
