from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None

# Fernet tokens are urlsafe-base64 payloads whose first byte is the version
# marker 0x80, so every valid token starts with this prefix.
_FERNET_TOKEN_PREFIX = "gAAAA"


class SecretKeyError(RuntimeError):
    """Raised when the persisted secret key exists but cannot be loaded."""


class DecryptionError(RuntimeError):
    """Raised when a Fernet-formatted value fails to decrypt."""


def _key_file_path() -> str:
    # 动态定位 data 目录，在开发及生产模式下均能顺畅使用
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, ".secret_key")


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

    # 2. 从本地敏感文件读取。文件存在但读取/解析失败时必须 fail-fast：
    #    绝不能重新生成密钥覆盖旧文件，否则所有已加密凭据将永久无法解密。
    key_file = _key_file_path()
    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                key_bytes = f.read().strip()
            _fernet = Fernet(key_bytes)
            return _fernet
        except Exception as exc:
            raise SecretKeyError(
                f"Secret key file exists at {key_file} but could not be loaded ({exc}). "
                "Refusing to regenerate the key because that would permanently destroy "
                "all previously encrypted credentials. Fix or restore the key file, "
                "or set NEWS_CAUGHT_SECRET_KEY explicitly."
            ) from exc

    # 3. 首次启动（文件不存在时）自动生成并写入权限 600 文件
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
    if not cipher_text.startswith(_FERNET_TOKEN_PREFIX):
        # 历史遗留明文数据（写入加密逻辑之前保存的值），原样返回。
        logger.info("Stored secret is not a Fernet token; treating it as legacy plaintext")
        return cipher_text
    fernet = _init_fernet()
    try:
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.error(
            "Failed to decrypt a Fernet-formatted secret (wrong key or corrupted data): %s", exc
        )
        raise DecryptionError(
            "Failed to decrypt stored secret: the encryption key does not match or the "
            "data is corrupted. Check the .secret_key file / NEWS_CAUGHT_SECRET_KEY, "
            "or re-enter the credential."
        ) from exc
