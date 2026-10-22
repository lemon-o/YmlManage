import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import PROFILES_DIR
from ..yaml_manager import YamlManager
from ..remote_uploader import RemoteUploader, load_remote_targets, save_remote_targets

router = APIRouter(prefix="/api/remote", tags=["Remote"])


class RemoteTargetModel(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="目标备注名称，如: OpenWrt主路由")
    protocol: str = Field(..., description="协议类型: webdav | ftp | smb | local")
    url: Optional[str] = Field(default="", description="WebDAV 完整 URL")
    server: Optional[str] = Field(default="", description="SMB 服务器地址")
    host: Optional[str] = Field(default="", description="主机地址 (FTP / SMB)")
    port: Optional[int] = Field(default=None, description="端口 (FTP默认为21，SMB默认为445)")
    share: Optional[str] = Field(default="", description="SMB 共享名称")
    path: Optional[str] = Field(default="", description="远程保存路径或文件名")
    username: Optional[str] = Field(default="", description="用户名")
    password: Optional[str] = Field(default="", description="密码")
    overwrite: bool = Field(default=True, description="是否默认覆盖替换")


class UploadProfileRequest(BaseModel):
    profile_name: str = Field(..., description="要上传的母本名称")
    protocol: str = Field(..., description="协议类型: webdav | ftp | smb | local")
    config: Dict[str, Any] = Field(..., description="远程连接与路径配置")
    overwrite: bool = Field(default=True, description="是否默认覆盖替换，默认 True")
    save_target: bool = Field(default=False, description="是否同时保存为常用目标")
    target_name: Optional[str] = Field(default="", description="若保存为常用目标时的名称")


class TestConnectionRequest(BaseModel):
    protocol: str = Field(..., description="协议类型: webdav | ftp | smb | local")
    config: Dict[str, Any] = Field(..., description="远程连接与路径配置")


@router.get("/targets")
def get_targets():
    """获取所有已保存的常用远程上传目标"""
    return load_remote_targets()


@router.post("/targets")
def save_target(target: RemoteTargetModel):
    """保存或更新常用远程上传目标"""
    targets = load_remote_targets()
    target_dict = target.dict()
    if not target_dict.get("id"):
        target_dict["id"] = f"target_{uuid.uuid4().hex[:8]}"
        targets.append(target_dict)
    else:
        for idx, item in enumerate(targets):
            if item.get("id") == target_dict["id"]:
                targets[idx] = target_dict
                break
        else:
            targets.append(target_dict)

    save_remote_targets(targets)
    return {"success": True, "target": target_dict}


@router.delete("/targets/{target_id}")
def delete_target(target_id: str):
    """删除指定的常用远程上传目标"""
    targets = load_remote_targets()
    new_targets = [t for t in targets if t.get("id") != target_id]
    save_remote_targets(new_targets)
    return {"success": True, "message": "已删除该常用目标"}


@router.post("/test")
def test_remote_target(req: TestConnectionRequest):
    """测试指定的远程连接是否通畅"""
    try:
        res = RemoteUploader.test_connection(req.protocol, req.config)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
def upload_profile(req: UploadProfileRequest):
    """
    将已编辑好的母本 YAML 配置文件上传推送到指定的远程目标 (支持 SMB / FTP / WebDAV / 本地，默认覆盖替换)
    """
    # 检查母本文件是否存在
    profile_path = YamlManager.get_profile_path(req.profile_name)
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"母本文件 {req.profile_name} 不存在")

    try:
        with open(profile_path, "rb") as f:
            content = f.read()

        result = RemoteUploader.upload(
            protocol=req.protocol,
            config=req.config,
            file_content=content,
            profile_name=profile_path.name,
            overwrite=req.overwrite
        )

        # 若勾选了保存为常用目标
        if req.save_target:
            t_name = (req.target_name or "").strip() or f"{req.protocol.upper()} 目标 ({req.config.get('server') or req.config.get('host') or req.config.get('url') or '未命名'})"
            target_data = {
                "id": f"target_{uuid.uuid4().hex[:8]}",
                "name": t_name,
                "protocol": req.protocol,
                "url": req.config.get("url", ""),
                "server": req.config.get("server") or req.config.get("host", ""),
                "host": req.config.get("host") or req.config.get("server", ""),
                "port": req.config.get("port"),
                "share": req.config.get("share", ""),
                "path": req.config.get("path", ""),
                "username": req.config.get("username", ""),
                "password": req.config.get("password", ""),
                "overwrite": req.overwrite
            }
            targets = load_remote_targets()
            targets.append(target_data)
            save_remote_targets(targets)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
