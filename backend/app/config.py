import os
from pathlib import Path

# 根目录与数据目录配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))

PROFILES_DIR = DATA_DIR / "profiles"
BACKUPS_DIR = DATA_DIR / "backups"
SOURCES_FILE = DATA_DIR / "sources.json"

# 根目录母本模板文件
ROOT_TEMPLATE_FILE = BASE_DIR / "母本模板.yml"

# 订阅分发保护 Token (空字符串表示无需 Token)
SUB_TOKEN = os.environ.get("SUB_TOKEN", "")

# 抓取外部订阅默认 User-Agent
DEFAULT_USER_AGENT = os.environ.get(
    "USER_AGENT",
    "Clash.Meta; ClashVerge/1.7.7; Clash/1.18.0"
)

# 默认测速与测延迟接口 (默认选用全球 Anycast 直连的 Cloudflare 204，国内外均畅通且不阻断海外节点)
DEFAULT_TEST_URL = os.environ.get(
    "DEFAULT_TEST_URL",
    "http://cp.cloudflare.com/generate_204"
)

# 常用国内直连与国际测速/延迟测试接口候选列表
DOMESTIC_TEST_URLS = [
    {
        "id": "cloudflare",
        "name": "Cloudflare 204 (全球 Anycast / 推荐)",
        "url": "http://cp.cloudflare.com/generate_204",
        "desc": "Cloudflare Anycast 全球 204，国内直连畅通，绝不阻断海外出站节点"
    },
    {
        "id": "google",
        "name": "Google 204 (Clash 原版 / 推荐)",
        "url": "http://www.gstatic.com/generate_204",
        "desc": "Clash 原版默认测速接口，海外节点延迟极低且精准"
    },
    {
        "id": "apple",
        "name": "Apple 204 (全球直连 / 稳定)",
        "url": "http://captive.apple.com/generate_204",
        "desc": "苹果官方连通测试，返回 204，国内国外均直连可通"
    },
    {
        "id": "microsoft",
        "name": "微软 Connect (全球通用)",
        "url": "http://www.msftconnecttest.com/connecttest.txt",
        "desc": "微软官方连通性探测接口，全球高可用"
    },
    {
        "id": "miui",
        "name": "小米 MIUI 204 (仅限国内直连)",
        "url": "http://connect.rom.miui.com/generate_204",
        "desc": "国内三网 CDN，注意：小米防火墙会直接阻断海外机房节点出站请求"
    },
    {
        "id": "huawei",
        "name": "华为 HiCloud 204 (仅限国内直连)",
        "url": "http://connectivitycheck.platform.hicloud.com/generate_204",
        "desc": "华为云连通性检测，注意：海外机房节点出站通常会被拒"
    },
    {
        "id": "vivo",
        "name": "vivo 204 (仅限国内直连)",
        "url": "http://wifi.vivo.com.cn/generate_204",
        "desc": "vivo 官方连通性探测，注意：海外机房节点出站通常会被拒"
    }
]

# 确保目录存在
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
