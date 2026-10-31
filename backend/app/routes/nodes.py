import json
import asyncio
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import DEFAULT_TEST_URL
from ..yaml_manager import YamlManager
from ..sub_fetcher import SubscriptionFetcher
from ..node_tester import test_and_filter_nodes_session, is_ad_or_fake_node

router = APIRouter(prefix="/api/nodes", tags=["Nodes"])


class FetchNodesRequest(BaseModel):
    url: str = Field(..., description="要提取的外部订阅链接")
    profile_name: str = Field(..., description="作为对比的目标母本名称")
    source_name: Optional[str] = Field(default=None, description="所属订阅源名称")
    custom_ua: Optional[str] = Field(default=None, description="自定义 User-Agent")
    filter_dead: Optional[bool] = Field(default=True, description="是否自动剔除没有延迟的节点")
    test_url: Optional[str] = Field(default=None, description="自定义测速/测延迟接口 URL")


def resolve_sub_source_name(req_source_name: Optional[str], url: str) -> str:
    """如果使用常用源提取节点，则记录提取到的节点绑定到常用源的名称"""
    if req_source_name and req_source_name.strip():
        return req_source_name.strip()
    try:
        from .sources import load_sources
        clean_url = (url or "").strip().lower().rstrip("/")
        if clean_url:
            sources = load_sources()
            for s in sources:
                s_url = s.get("url", "").strip().lower().rstrip("/")
                if s_url and s_url == clean_url:
                    if s.get("name"):
                        return str(s["name"]).strip()
            import urllib.parse
            req_host = urllib.parse.urlparse(clean_url).netloc.lower()
            if req_host:
                for s in sources:
                    s_url = s.get("url", "").strip().lower()
                    if s_url:
                        s_host = urllib.parse.urlparse(s_url).netloc.lower()
                        if s_host and (s_host == req_host or s_host in req_host or req_host in s_host):
                            if s.get("name"):
                                return str(s["name"]).strip()
                    s_name = s.get("name", "").strip().lower()
                    if s_name and len(s_name) >= 3 and s_name in clean_url:
                        return str(s["name"]).strip()
                return req_host
    except Exception:
        pass
    return "外部订阅"


class ImportNodesRequest(BaseModel):
    profile_name: str = Field(..., description="目标母本名称")
    nodes: List[Dict[str, Any]] = Field(..., description="勾选的待导入节点列表")
    target_groups: List[str] = Field(default=[], description="勾选的目标策略组名称列表")
    overwrite: bool = Field(default=True, description="若母本已存在同名节点，是否覆盖配置")


class TestNodesDelayRequest(BaseModel):
    nodes: List[Dict[str, Any]] = Field(..., description="要测试延迟的节点列表")
    test_url: Optional[str] = Field(default=None, description="测试 URL")
    timeout: Optional[float] = Field(default=3.5, description="超时秒数")


class IpLookupRequest(BaseModel):
    queries: List[str] = Field(..., description="要查询归属地的 IP 或域名列表")


_ip_geo_cache: Dict[str, Dict[str, Any]] = {}


def get_flag_emoji_py(country_code: str) -> str:
    """根据 ISO 两位国家代码转换国家旗帜 Emoji"""
    if not country_code or len(country_code) != 2:
        return "🌐"
    try:
        return "".join(chr(0x1F1E6 + ord(c.upper()) - ord("A")) for c in country_code)
    except Exception:
        return "🌐"


@router.post("/fetch-stream")
async def fetch_nodes_stream(req: FetchNodesRequest):
    """
    拉取外部订阅链接并流式返回提取进度与结果 (支持弹窗实时展示提取进度)
    """
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="订阅链接不能为空")

    async def event_generator():
        queue = asyncio.Queue()

        async def worker():
            try:
                await queue.put({
                    "type": "progress",
                    "step": 1,
                    "percent": 15,
                    "msg": "正在连接订阅服务器拉取配置数据...",
                    "stage": "fetching"
                })

                try:
                    raw_nodes = await SubscriptionFetcher.fetch_and_parse(req.url, req.custom_ua)
                except Exception as e:
                    await queue.put({
                        "type": "error",
                        "msg": f"抓取/解析订阅失败: {str(e)}"
                    })
                    await queue.put(None)
                    return

                total_raw = len(raw_nodes)
                if total_raw == 0:
                    await queue.put({
                        "type": "error",
                        "msg": "未能从此订阅中解析出任何有效代理节点，请确认链接是否有效"
                    })
                    await queue.put(None)
                    return

                await queue.put({
                    "type": "progress",
                    "step": 2,
                    "percent": 35,
                    "msg": f"订阅解析成功，共发现 {total_raw} 个原始代理节点",
                    "total_raw": total_raw,
                    "alive_count": 0,
                    "filtered_count": 0,
                    "stage": "parsed"
                })

                summary = YamlManager.get_profile_summary(req.profile_name)
                existing_names = set(summary.get("proxy_names", []))
                available_groups = summary.get("groups", [])
                active_test_url = (req.test_url.strip() if req.test_url and req.test_url.strip() else None) or summary.get("test_url") or DEFAULT_TEST_URL

                await queue.put({
                    "type": "progress",
                    "step": 3,
                    "percent": 45,
                    "msg": "正在启动 Mihomo 核心并构建并发探测隧道...",
                    "total_raw": total_raw,
                    "alive_count": 0,
                    "filtered_count": 0,
                    "stage": "starting_core"
                })

                last_reported_time = [0.0]

                async def on_delay_progress(comp, tot, alive):
                    now = time.time()
                    if comp == tot or (now - last_reported_time[0]) >= 0.08:
                        last_reported_time[0] = now
                        pct = 45 + int((comp / max(1, tot)) * 45)
                        filtered = comp - alive
                        await queue.put({
                            "type": "progress",
                            "step": 3,
                            "percent": pct,
                            "msg": f"并发延迟探测中: {comp}/{tot} (有效 {alive}，已过滤 {filtered})",
                            "total_raw": total_raw,
                            "alive_count": alive,
                            "filtered_count": filtered,
                            "completed": comp,
                            "stage": "probing"
                        })

                # 并发执行真实延迟测试（保留全部节点，以便前端可在“本次提取(全部)”和“有效可用”卡片间切换查看）
                await test_and_filter_nodes_session(
                    raw_nodes,
                    test_url=active_test_url,
                    concurrency=25,
                    timeout=3.5,
                    filter_dead=False,
                    on_progress=on_delay_progress
                )

                processed_nodes = []
                new_count = 0
                existing_count = 0
                alive_count = 0
                filtered_count = 0
                resolved_sub_source = resolve_sub_source_name(req.source_name, req.url)

                for idx, node in enumerate(raw_nodes):
                    name = str(node.get("name", f"Node-{idx+1}"))
                    is_existing = name in existing_names
                    if is_existing:
                        existing_count += 1
                    else:
                        new_count += 1

                    # 附带订阅源归属字段
                    node_sub = str(node.get("sub_source") or resolved_sub_source)
                    node["sub_source"] = node_sub

                    delay = node.get("delay", -1)
                    is_ad = is_ad_or_fake_node(node)
                    is_alive = (not is_ad) and (delay > 0)
                    is_filtered = not is_alive
                    filter_reason = "广告/非节点" if is_ad else ("超时" if delay <= 0 else "")

                    node["is_filtered"] = is_filtered
                    node["filter_reason"] = filter_reason

                    if is_alive:
                        alive_count += 1
                    else:
                        filtered_count += 1

                    p_type = str(node.get("type", "unknown")).lower()
                    if node.get("ports"):
                        proto_display = f"{p_type} / 端口跳跃({node.get('ports')})"
                    elif node.get("xudp"):
                        proto_display = f"{p_type} / xudp"
                    elif node.get("udp"):
                        proto_display = f"{p_type} / udp"
                    elif node.get("network"):
                        proto_display = f"{p_type} / {node.get('network')}"
                    else:
                        proto_display = p_type

                    processed_nodes.append({
                        "id": f"node_{idx}",
                        "proxy_key": node.get("proxy_key", f"P_{idx}"),
                        "name": name,
                        "type": p_type,
                        "proto_display": proto_display,
                        "server": str(node.get("server", "")),
                        "port": str(node.get("ports") or node.get("port") or ""),
                        "delay": delay,
                        "is_filtered": is_filtered,
                        "filter_reason": filter_reason,
                        "is_existing": is_existing,
                        "sub_source": node_sub,
                        "raw": node
                    })

                await queue.put({
                    "type": "done",
                    "step": 4,
                    "percent": 100,
                    "msg": f"提取与延迟过滤完成！共 {total_raw} 个原始节点 (有效 {alive_count}，已过滤 {filtered_count})",
                    "total_raw": total_raw,
                    "total": len(processed_nodes),
                    "alive_count": alive_count,
                    "filtered_count": filtered_count,
                    "new_count": new_count,
                    "existing_count": existing_count,
                    "nodes": processed_nodes,
                    "available_groups": available_groups,
                    "stage": "done"
                })
            except Exception as e:
                await queue.put({
                    "type": "error",
                    "msg": f"提取过程中发生异常: {str(e)}"
                })
            finally:
                await queue.put(None)

        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield json.dumps(item) + "\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/fetch")
async def fetch_nodes_from_subscription(req: FetchNodesRequest):
    """
    常规 HTTP 请求拉取外部订阅链接并提取节点列表
    """
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="订阅链接不能为空")

    try:
        raw_nodes = await SubscriptionFetcher.fetch_and_parse(req.url, req.custom_ua)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"抓取/解析订阅失败: {str(e)}")

    total_raw = len(raw_nodes)
    if total_raw == 0:
        return {
            "total_raw": 0,
            "total": 0,
            "filtered_count": 0,
            "new_count": 0,
            "existing_count": 0,
            "nodes": [],
            "available_groups": [],
            "message": "未能从此订阅中解析出任何有效节点，请确认链接是否有效"
        }

    summary = YamlManager.get_profile_summary(req.profile_name)
    existing_names = set(summary.get("proxy_names", []))
    available_groups = summary.get("groups", [])
    active_test_url = (req.test_url.strip() if req.test_url and req.test_url.strip() else None) or summary.get("test_url") or DEFAULT_TEST_URL

    await test_and_filter_nodes_session(
        raw_nodes,
        test_url=active_test_url,
        concurrency=25,
        timeout=3.5,
        filter_dead=False
    )

    processed_nodes = []
    new_count = 0
    existing_count = 0
    alive_count = 0
    filtered_count = 0
    resolved_sub_source = resolve_sub_source_name(req.source_name, req.url)

    for idx, node in enumerate(raw_nodes):
        name = str(node.get("name", f"Node-{idx+1}"))
        is_existing = name in existing_names
        if is_existing:
            existing_count += 1
        else:
            new_count += 1

        # 附带订阅源归属字段
        node_sub = str(node.get("sub_source") or resolved_sub_source)
        node["sub_source"] = node_sub

        delay = node.get("delay", -1)
        is_ad = is_ad_or_fake_node(node)
        is_alive = (not is_ad) and (delay > 0)
        is_filtered = not is_alive
        filter_reason = "广告/非节点" if is_ad else ("超时" if delay <= 0 else "")

        node["is_filtered"] = is_filtered
        node["filter_reason"] = filter_reason

        if is_alive:
            alive_count += 1
        else:
            filtered_count += 1

        p_type = str(node.get("type", "unknown")).lower()
        if node.get("ports"):
            proto_display = f"{p_type} / 端口跳跃({node.get('ports')})"
        elif node.get("xudp"):
            proto_display = f"{p_type} / xudp"
        elif node.get("udp"):
            proto_display = f"{p_type} / udp"
        elif node.get("network"):
            proto_display = f"{p_type} / {node.get('network')}"
        else:
            proto_display = p_type

        processed_nodes.append({
            "id": f"node_{idx}",
            "proxy_key": node.get("proxy_key", f"P_{idx}"),
            "name": name,
            "type": p_type,
            "proto_display": proto_display,
            "server": str(node.get("server", "")),
            "port": str(node.get("ports") or node.get("port") or ""),
            "delay": delay,
            "is_filtered": is_filtered,
            "filter_reason": filter_reason,
            "is_existing": is_existing,
            "sub_source": node_sub,
            "raw": node
        })

    return {
        "total_raw": total_raw,
        "total": len(processed_nodes),
        "alive_count": alive_count,
        "filtered_count": filtered_count,
        "new_count": new_count,
        "existing_count": existing_count,
        "nodes": processed_nodes,
        "available_groups": available_groups
    }


@router.post("/import")
def import_selected_nodes(req: ImportNodesRequest):
    """
    将用户选中的节点注入母本，并手动加入指定的策略组
    """
    if not req.nodes:
        raise HTTPException(status_code=400, detail="未勾选任何要导入的节点")

    nodes_payload = []
    for item in req.nodes:
        if "raw" in item and isinstance(item["raw"], dict):
            raw_node = dict(item["raw"])
            if "sub_source" in item and item["sub_source"]:
                raw_node["sub_source"] = item["sub_source"]
            nodes_payload.append(raw_node)
        elif isinstance(item, dict) and "name" in item:
            nodes_payload.append(item)

    try:
        result = YamlManager.inject_nodes(
            profile_name=req.profile_name,
            nodes_to_import=nodes_payload,
            target_group_names=req.target_groups,
            overwrite=req.overwrite
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/test-delays")
async def test_nodes_delay_endpoint(req: TestNodesDelayRequest):
    """
    直接对传入的节点列表执行真实 URL Test 延迟测试，返回每个节点的 delay
    """
    if not req.nodes:
        return {"delays": {}}

    active_test_url = (req.test_url.strip() if req.test_url and req.test_url.strip() else None) or DEFAULT_TEST_URL
    results = await test_and_filter_nodes_session(
        req.nodes,
        test_url=active_test_url,
        concurrency=25,
        timeout=req.timeout or 3.5,
        filter_dead=False  # 不过滤，全部返回以便显示延迟或超时
    )
    delays_map = {n.get("name"): n.get("delay", -1) for n in results}
    return {"delays": delays_map}


@router.post("/ip-lookup")
async def batch_lookup_ips(req: IpLookupRequest):
    """
    批量查询 IP 或域名的归属国家与区域信息 (带内存缓存与极速批处理)
    """
    import socket
    import httpx

    results: Dict[str, Any] = {}
    missing_queries: List[str] = []

    for q in req.queries:
        clean_q = str(q).strip()
        if not clean_q or clean_q in ["127.0.0.1", "localhost", "0.0.0.0"]:
            continue
        if clean_q in _ip_geo_cache:
            results[clean_q] = _ip_geo_cache[clean_q]
        else:
            missing_queries.append(clean_q)

    if not missing_queries:
        return {"data": results}

    # 去重并限制单次批查上限
    missing_queries = list(dict.fromkeys(missing_queries))[:60]
    loop = asyncio.get_event_loop()
    batch_payload = []
    reverse_map = {}

    for q in missing_queries:
        ip_candidate = q
        is_ip = False
        parts = q.split(".")
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            is_ip = True
        elif ":" in q:
            is_ip = True

        if not is_ip:
            try:
                addrinfo = await asyncio.wait_for(
                    loop.getaddrinfo(q, None, family=socket.AF_INET),
                    timeout=1.5
                )
                if addrinfo:
                    ip_candidate = addrinfo[0][4][0]
            except Exception:
                pass

        reverse_map[ip_candidate] = q
        batch_payload.append({"query": ip_candidate, "lang": "zh-CN"})

    if batch_payload:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post("http://ip-api.com/batch", json=batch_payload)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data:
                        orig_query = reverse_map.get(item.get("query"), item.get("query"))
                        if item.get("status") == "success":
                            c_code = item.get("countryCode", "")
                            flag = get_flag_emoji_py(c_code)
                            geo_info = {
                                "country": item.get("country", "未知国家"),
                                "countryCode": c_code,
                                "region": item.get("regionName", ""),
                                "city": item.get("city", ""),
                                "flag": flag,
                                "isp": item.get("isp", "")
                            }
                            _ip_geo_cache[orig_query] = geo_info
                            results[orig_query] = geo_info
        except Exception:
            pass

    return {"data": results}

