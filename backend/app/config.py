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

# 每个母本保留快照数量上限（默认最多保留最新的 20 份）
MAX_BACKUPS_PER_PROFILE = int(os.environ.get("MAX_BACKUPS_PER_PROFILE", "20"))

# 订阅分发保护 Token (空字符串表示无需 Token)
SUB_TOKEN = os.environ.get("SUB_TOKEN", "")

# 抓取外部订阅默认 User-Agent
DEFAULT_USER_AGENT = os.environ.get(
    "USER_AGENT",
    "Clash.Meta; ClashVerge/1.7.7; Clash/1.18.0"
)

# 默认 URL Test 延迟测试接口 (对标 NekoBox 逻辑，默认选用全球 Anycast 直连的 Cloudflare 204)
DEFAULT_TEST_URL = os.environ.get(
    "DEFAULT_TEST_URL",
    "http://cp.cloudflare.com/generate_204"
)

# 常用 URL Test 延迟测试接口候选列表 (支持国内与海外主流探针)
DOMESTIC_TEST_URLS = [
    {
        "id": "cloudflare",
        "name": "Cloudflare 204 (NekoBox 推荐 / 全球)",
        "url": "http://cp.cloudflare.com/generate_204",
        "desc": "Cloudflare Anycast 全球 204，国内直连畅通，海外出站极速响应 (NekoBox 首选)"
    },
    {
        "id": "google",
        "name": "Google 204 (NekoBox 标准 / 原版)",
        "url": "http://www.gstatic.com/generate_204",
        "desc": "Google 官方 204 探针，NekoBox / Clash 原生标准，海外节点精准 RTT"
    },
    {
        "id": "apple",
        "name": "Apple 204 (全球 Anycast 直连)",
        "url": "http://captive.apple.com/generate_204",
        "desc": "苹果官方网络连通探测接口，全球毫秒级响应，国内国外均畅通"
    },
    {
        "id": "microsoft",
        "name": "微软 Connect (全球通用)",
        "url": "http://www.msftconnecttest.com/connecttest.txt",
        "desc": "微软官方连通性探测接口，全球高可用"
    },
    {
        "id": "miui",
        "name": "小米 MIUI 204 (国内内网直连)",
        "url": "http://connect.rom.miui.com/generate_204",
        "desc": "国内三网 CDN，注意：海外节点访问属出境再回国线路，延迟会偏高"
    },
    {
        "id": "huawei",
        "name": "华为 HiCloud 204 (国内内网直连)",
        "url": "http://connectivitycheck.platform.hicloud.com/generate_204",
        "desc": "华为云国内连通性检测，海外节点访问延迟偏高"
    },
    {
        "id": "vivo",
        "name": "vivo 204 (国内内网直连)",
        "url": "http://wifi.vivo.com.cn/generate_204",
        "desc": "vivo 官方连通性探测，海外节点访问延迟偏高"
    }
]

# 确保目录存在
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
