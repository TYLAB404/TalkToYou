import os
import base64
import hashlib
from cryptography.fernet import Fernet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_FILE = os.path.join(BASE_DIR, ".secret_key")

def _get_fernet() -> Fernet:
    """获取或初始化本地专属加密秘钥（存储在 .secret_key，严禁上传 Git）"""
    if os.path.exists(SECRET_FILE):
        try:
            with open(SECRET_FILE, "rb") as f:
                key = f.read().strip()
                if len(key) == 44:
                    return Fernet(key)
        except Exception:
            pass

    # 若不存在，依据本地唯一特征生成安全加密秘钥
    new_key = Fernet.generate_key()
    try:
        with open(SECRET_FILE, "wb") as f:
            f.write(new_key)
    except Exception as e:
        print(f"[Security] 写入本地密钥文件失败: {e}")
    return Fernet(new_key)

def encrypt_str(plaintext: str) -> str:
    """将敏感字符串（如 API Key）安全加密为密文"""
    if not plaintext or not isinstance(plaintext, str):
        return ""
    plaintext = plaintext.strip()
    # 如果已经是 Fernet 格式密文则不重复加密
    if plaintext.startswith("gAAAAA") and len(plaintext) > 50:
        return plaintext
    try:
        f = _get_fernet()
        token = f.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")
    except Exception as e:
        print(f"[Security] 加密失败: {e}")
        return plaintext

def decrypt_str(token_or_plain: str) -> str:
    """解密密文字符串，若非密文或解密失败则原样返回"""
    if not token_or_plain or not isinstance(token_or_plain, str):
        return ""
    token_or_plain = token_or_plain.strip()
    if not (token_or_plain.startswith("gAAAAA") and len(token_or_plain) > 50):
        # 明文直接返回
        return token_or_plain
    try:
        f = _get_fernet()
        decrypted = f.decrypt(token_or_plain.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception as e:
        print(f"[Security] 解密失败: {e}")
        return token_or_plain

def mask_api_key(key: str) -> str:
    """脱敏展示 API Key，如 b3e2****3313"""
    if not key or len(key) < 8:
        return key or ""
    # 若是密文先解密后脱敏
    plain = decrypt_str(key)
    if len(plain) <= 8:
        return "****"
    return f"{plain[:4]}****{plain[-4:]}"
