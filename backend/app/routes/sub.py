import urllib.parse
from fastapi import APIRouter, HTTPException, Query, Response
from ..config import SUB_TOKEN
from ..yaml_manager import YamlManager

router = APIRouter(tags=["Subscription Export"])


@router.get("/sub/{profile_name}")
def export_subscription(
    profile_name: str,
    token: str = Query(default="", description="安全访问 Token")
):
    """
    外部客户端直接拉取该母本 YAML 配置作为订阅
    """
    if SUB_TOKEN and token != SUB_TOKEN:
        raise HTTPException(status_code=403, detail="无权访问，Token 不正确")

    # 去除可能携带的 .yaml 后缀匹配
    clean_name = profile_name
    if not clean_name.endswith((".yaml", ".yml")):
        clean_name += ".yaml"

    try:
        content = YamlManager.get_raw_yaml(clean_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="母本文件不存在")

    encoded_filename = urllib.parse.quote(clean_name)

    return Response(
        content=content,
        media_type="text/yaml; charset=utf-8",
        headers={
            "Content-Disposition": f"inline; filename=\"config.yaml\"; filename*=UTF-8''{encoded_filename}",
            "profile-update-interval": "24",
            "subscription-userinfo": "upload=0; download=0; total=1099511627776; expire=0"
        }
    )
