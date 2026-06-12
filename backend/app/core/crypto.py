from __future__ import annotations

import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _init_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    # 1. 尝试从环境变量读取
    key_env = os.getenv("NEWS_CAUGHT_SECRET_KEY")
    if key_env:
        try:
            _fernet = Fernet(key_env.encode("utf-8"))
            return _fernet
        except Exception as exc:
            logger.error("Invalid NEWS_CAUGHT_SECRET_KEY env variable: %s", exc)

    # 2. 从本地敏感文件读取/生成
    # 动态定位 data 目录，在开发及生产模式下均能顺畅使用
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)

    key_file = os.path.join(base_dir, ".secret_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                key_bytes = f.read().strip()
            _fernet = Fernet(key_bytes)
            return _fernet
        except Exception as exc:
            logger.warning("Failed to load secret key file: %s. Re-generating...", exc)

    # 3. 首次启动自动生成并写入权限 600 文件
    try:
        new_key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(new_key)
        try:
            os.chmod(key_file, 0o600)
        except Exception:
            logger.warning("Failed to set chmod 600 on secret key file")
        _fernet = Fernet(new_key)
        logger.info("Generated new secret key and saved to %s", key_file)
        return _fernet
    except Exception as exc:
        logger.error("Failed to generate secret key: %s", exc)
        # Fallback to a temp key in memory so system doesn't crash, though it won't persist across restarts
        temp_key = Fernet.generate_key()
        _fernet = Fernet(temp_key)
        return _fernet


def encrypt_key(plain_text: str | None) -> str:
    if not plain_text:
        return ""
    fernet = _init_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_key(cipher_text: str | None) -> str:
    if not cipher_text:
        return ""
    fernet = _init_fernet()
    try:
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        # 如果原来就是明文（或者是解密失败），尝试返回原字符串
        logger.debug("Failed to decrypt value (could be plaintext or invalid key): %s", exc)
        return cipher_text
