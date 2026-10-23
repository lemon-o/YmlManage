import os
import json
import time
import hmac
import hashlib
import secrets
import base64
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from .config import DATA_DIR

AUTH_FILE = DATA_DIR / "auth.json"


def is_running_in_docker() -> bool:
    """判断当前服务是否运行在 Docker 容器中"""
    # 1. 显式环境变量判断 (Dockerfile / docker-compose.yml 注入)
    if os.environ.get("RUN_ENV", "").lower() == "docker":
        return True
    if os.environ.get("IS_DOCKER", "").lower() in ("1", "true", "yes"):
        return True

    # 2. 容器特征文件判断
    if Path("/.dockerenv").exists():
        return True

    # 3. /proc/1/cgroup 检查
    try:
        cgroup = Path("/proc/1/cgroup")
        if cgroup.exists() and "docker" in cgroup.read_text(encoding="utf-8", errors="ignore"):
            return True
    except Exception:
        pass

    return False


def is_auth_required() -> bool:
    """
    判断当前环境是否要求启用访问密码验证
    规则：
      - 若显式配置了 REQUIRE_AUTH 环境变量，以其为准 (true/false)
      - 默认规则：Docker 容器环境必须启用 (True)，本地电脑/开发环境无需密码 (False)
    """
    req_env = os.environ.get("REQUIRE_AUTH")
    if req_env is not None:
        return req_env.lower() in ("1", "true", "yes")

    return is_running_in_docker()


class AuthManager:
    """管理访问密码及安全令牌的存取与验证"""

    @classmethod
    def _load_auth_data(cls) -> Optional[Dict[str, Any]]:
        if not AUTH_FILE.exists():
            return None
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f">> [Auth] 读取 auth.json 失败: {e}")
            return None

    @classmethod
    def _save_auth_data(cls, data: Dict[str, Any]) -> None:
        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def is_initialized(cls) -> bool:
        """检查系统是否已初始化过密码"""
        data = cls._load_auth_data()
        return bool(data and data.get("password_hash") and data.get("salt"))

    @classmethod
    def _hash_password(cls, password: str, salt_hex: str) -> str:
        """使用 PBKDF2-HMAC-SHA256 安全哈希算法 (迭代 100,000 次)"""
        salt = bytes.fromhex(salt_hex)
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000
        ).hex()

    @classmethod
    def set_password(cls, new_password: str) -> str:
        """
        初始化或更新访问密码，并返回生成的登录凭证 Token
        """
        if not new_password or len(new_password.strip()) < 1:
            raise ValueError("密码不能为空")

        new_password = new_password.strip()
        salt_hex = secrets.token_hex(16)
        secret_key = secrets.token_hex(32)
        pwd_hash = cls._hash_password(new_password, salt_hex)

        auth_data = {
            "is_initialized": True,
            "password_hash": pwd_hash,
            "salt": salt_hex,
            "secret_key": secret_key,
            "updated_at": int(time.time())
        }
        cls._save_auth_data(auth_data)

        # 生成初始登录 Token (30 天有效)
        return cls.create_token(secret_key)

    @classmethod
    def verify_password(cls, password: str) -> Tuple[bool, Optional[str]]:
        """
        验证用户输入的密码是否正确
        返回值: (是否匹配, 如果匹配则生成并返回新 Token，否则返回 None)
        """
        data = cls._load_auth_data()
        if not data or not data.get("password_hash") or not data.get("salt"):
            return False, None

        salt_hex = data["salt"]
        stored_hash = data["password_hash"]
        secret_key = data.get("secret_key")
        if not secret_key:
            # 兼容老数据补充 secret_key
            secret_key = secrets.token_hex(32)
            data["secret_key"] = secret_key
            cls._save_auth_data(data)

        computed_hash = cls._hash_password(password.strip(), salt_hex)
        if hmac.compare_digest(computed_hash, stored_hash):
            token = cls.create_token(secret_key)
            return True, token

        return False, None

    @classmethod
    def create_token(cls, secret_key: Optional[str] = None, expires_days: int = 30) -> str:
        """生成带 HMAC-SHA256 签名的无状态安全会话 Token"""
        if not secret_key:
            data = cls._load_auth_data() or {}
            secret_key = data.get("secret_key") or "fallback_secret_key"

        payload = {
            "exp": int(time.time()) + expires_days * 86400,
            "iat": int(time.time()),
            "nonce": secrets.token_hex(8)
        }
        b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        sig = hmac.new(
            secret_key.encode("utf-8"),
            b64_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return f"{b64_payload}.{sig}"

    @classmethod
    def verify_token(cls, token: str) -> bool:
        """校验 Token 签名是否合法且未过期"""
        if not token:
            return False

        try:
            parts = token.split(".")
            if len(parts) != 2:
                return False

            b64_payload, sig = parts
            data = cls._load_auth_data()
            if not data or not data.get("secret_key"):
                return False

            secret_key = data["secret_key"]
            expected_sig = hmac.new(
                secret_key.encode("utf-8"),
                b64_payload.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(sig, expected_sig):
                return False

            # 解码 payload 并验证过期时间
            padded_b64 = b64_payload + "=" * ((4 - len(b64_payload) % 4) % 4)
            payload_str = base64.urlsafe_b64decode(padded_b64.encode("utf-8")).decode("utf-8")
            payload = json.loads(payload_str)

            if time.time() > payload.get("exp", 0):
                return False

            return True
        except Exception:
            return False
