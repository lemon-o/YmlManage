import os
import shutil
from pathlib import Path
from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .config import PROFILES_DIR, ROOT_TEMPLATE_FILE
from .routes import profiles, sources, nodes, sub, remote, auth
from .routes.profiles import get_default_template_content
from .auth import is_auth_required, AuthManager
from .routes.auth import extract_token_from_request

app = FastAPI(
    title="YmlManage - 节点母本维护管理平台",
    description="维护 Clash/Mihomo 母本配置文件，从外部订阅提取节点勾选导入并分发",
    version="1.4.4"
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启用 GZip 压缩，任何大于 1000 字节的静态资源/接口自动压缩，极大缩短公网传输等待时间
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def auth_security_middleware(request: Request, call_next):
    """
    环境安全守卫中间件：
    - Docker 环境或强制配置开启认证时，除白名单接口外，全部校验密码 Token
    - 本地开发/本机电脑运行环境自动免密放行
    """
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path

    # 仅拦截 /api/ 保护路由，放行静态资源、前端单页路由以及订阅链接 /sub/{name}
    if path.startswith("/api/"):
        public_api_prefixes = (
            "/api/auth/status",
            "/api/auth/init",
            "/api/auth/login"
        )
        if not any(path.startswith(prefix) for prefix in public_api_prefixes):
            if is_auth_required():
                # 检查系统是否初始化
                if not AuthManager.is_initialized():
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "系统尚未初始化访问密码，请先完成密码设置", "code": "NOT_INITIALIZED"}
                    )

                auth_header = request.headers.get("Authorization")
                x_token = request.headers.get("X-Auth-Token")
                token = extract_token_from_request(auth_header, x_token)

                if not token or not AuthManager.verify_token(token):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "未授权或登录凭证已过期，请重新登录", "code": "UNAUTHORIZED"}
                    )

    return await call_next(request)


# 挂载 API 路由
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(sources.router)
app.include_router(nodes.router)
app.include_router(sub.router)
app.include_router(remote.router)

SVG_FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="8" fill="#2563eb"/>
  <path d="M8 16h16M16 8v16" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round"/>
  <circle cx="16" cy="16" r="4" fill="#ffffff"/>
  <circle cx="8" cy="16" r="2.2" fill="#93c5fd"/>
  <circle cx="24" cy="16" r="2.2" fill="#93c5fd"/>
  <circle cx="16" cy="8" r="2.2" fill="#93c5fd"/>
  <circle cx="16" cy="24" r="2.2" fill="#93c5fd"/>
</svg>"""


@app.get("/favicon.ico")
def get_favicon():
    """纯矢量科技网络节点 Favicon (解决浏览器历史 emoji 缓存)"""
    return Response(
        content=SVG_FAVICON,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


@app.on_event("startup")
def init_default_data():
    """首次启动时，若母本目录为空，则自动基于【母本模板.yml】生成默认母本"""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    # 清理历史旧的优选节点文件
    old_file = PROFILES_DIR / "优选节点.yaml"
    if old_file.exists():
        try:
            old_file.unlink()
        except Exception:
            pass
    
    preferred_file = PROFILES_DIR / "母本模板.yaml"
    if not preferred_file.exists():
        if ROOT_TEMPLATE_FILE.exists():
            shutil.copy2(ROOT_TEMPLATE_FILE, preferred_file)
            print(f">> [初始化] 已成功将根目录【{ROOT_TEMPLATE_FILE.name}】载入为默认母本: 母本模板.yaml")
        else:
            with open(preferred_file, "w", encoding="utf-8") as f:
                f.write(get_default_template_content())
            print(">> [初始化] 已创建默认母本: 母本模板.yaml")


# 静态文件前端托管
STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = STATIC_DIR / "assets"
if STATIC_DIR.exists():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    class CachedStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    app.mount("/assets", CachedStaticFiles(directory=ASSETS_DIR), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            resp = FileResponse(file_path)
            if full_path.startswith("assets/"):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        resp = FileResponse(STATIC_DIR / "index.html")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp
else:
    @app.get("/")
    def index():
        return {
            "message": "YmlManage 后端运行中",
            "docs": "/docs",
            "api": "/api/profiles"
        }
