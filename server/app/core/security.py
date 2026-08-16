"""安全原语：口令哈希（PBKDF2）、JWT、敏感字段 AES-GCM 加解密。

红线：口令类钓鱼表单字段永不落库（见 landing 服务），此处仅用于平台账号口令与配置密文。
生产环境 AES 密钥应接 KMS，勿依赖 SECRET_KEY 派生。
"""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings
from .errors import BizError, ErrorCode

_PBKDF2_ITERATIONS = 200_000
_ALG = "HS256"


# ---------- 口令哈希 ----------

def hash_password(raw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(raw: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", raw.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False


# ---------- JWT ----------

def create_token(account_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALG)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALG])
    except jwt.ExpiredSignatureError:
        raise BizError(ErrorCode.TOKEN_EXPIRED)
    except jwt.InvalidTokenError:
        raise BizError(ErrorCode.UNAUTHORIZED)


# ---------- AES-GCM 敏感配置加解密 ----------

def _aes_key() -> bytes:
    if settings.aes_key_b64:
        key = base64.b64decode(settings.aes_key_b64)
        if len(key) != 32:
            raise ValueError("AES_KEY_B64 必须为 32 字节 base64")
        return key
    # 开发环境兜底：从 SECRET_KEY 派生（生产禁止依赖此路径）
    return hashlib.sha256(settings.secret_key.encode()).digest()


def encrypt_secret(plain: str) -> bytes:
    """返回 nonce(12B) || ciphertext。"""
    nonce = os.urandom(12)
    ct = AESGCM(_aes_key()).encrypt(nonce, plain.encode(), None)
    return nonce + ct


def decrypt_secret(blob: bytes) -> str:
    return AESGCM(_aes_key()).decrypt(blob[:12], blob[12:], None).decode()
