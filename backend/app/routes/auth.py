from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field
from typing import Optional
from ..auth import is_running_in_docker, is_auth_required, AuthManager

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class InitPasswordRequest(BaseModel):
    password: str = Field(..., min_length=1, description="新设置的访问密码")
    confirm_password: str = Field(..., min_length=1, description="确认密码")


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, description="访问密码")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="旧访问密码")
    new_password: str = Field(..., min_length=1, description="新访问密码")
    confirm_password: str = Field(..., min_length=1, description="确认新密码")


def extract_token_from_request(
    authorization: Optional[str] = None,
    x_auth_token: Optional[str] = None
) -> Optional[str]:
    """从请求头提取 Bearer Token 或 X-Auth-Token"""
    if x_auth_token:
        return x_auth_token.strip()
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return authorization.strip()
    return None


@router.get("/status")
def get_auth_status(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None)
):
    """
    获取当前系统的认证状态：
    - 是否运行在 Docker
    - 是否必须进行网页密码认证
    - 是否已完成初始化
    - 当前请求是否处于已登录状态
    """
    docker_mode = is_running_in_docker()
    auth_req = is_auth_required()
    is_init = AuthManager.is_initialized()

    # 如果不需要认证（例如本地电脑开发环境），直接免密判定为已登录
    if not auth_req:
        return {
            "auth_required": False,
            "is_docker": docker_mode,
            "is_initialized": True,
            "logged_in": True
        }

    token = extract_token_from_request(authorization, x_auth_token)
    logged_in = False
    if token and is_init:
        logged_in = AuthManager.verify_token(token)

    return {
        "auth_required": True,
        "is_docker": docker_mode,
        "is_initialized": is_init,
        "logged_in": logged_in
    }


@router.post("/init")
def initialize_password(req: InitPasswordRequest):
    """
    系统首次初始化设置访问密码
    """
    if AuthManager.is_initialized():
        raise HTTPException(status_code=400, detail="系统访问密码已初始化过，如需修改请使用修改密码功能")

    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致，请重新检查")

    try:
        token = AuthManager.set_password(req.password)
        return {
            "message": "访问密码初始化成功",
            "token": token
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置密码失败: {str(e)}")


@router.post("/login")
def login(req: LoginRequest):
    """
    用户输入密码进行身份验证
    """
    if not AuthManager.is_initialized():
        raise HTTPException(status_code=400, detail="系统尚未初始化访问密码，请先完成初始化设置")

    ok, token = AuthManager.verify_password(req.password)
    if not ok or not token:
        raise HTTPException(status_code=401, detail="访问密码错误，请重新输入")

    return {
        "message": "登录成功",
        "token": token
    }


@router.post("/logout")
def logout():
    """
    登出清理
    """
    return {"message": "已成功退出登录"}


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None)
):
    """
    修改已有的访问密码
    """
    if is_auth_required():
        token = extract_token_from_request(authorization, x_auth_token)
        if not token or not AuthManager.verify_token(token):
            raise HTTPException(status_code=401, detail="未授权或登录已过期，请重新登录后再操作")

    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")

    # 校验旧密码
    ok, _ = AuthManager.verify_password(req.old_password)
    if not ok:
        raise HTTPException(status_code=400, detail="原访问密码不正确")

    new_token = AuthManager.set_password(req.new_password)
    return {
        "message": "密码修改成功",
        "token": new_token
    }
