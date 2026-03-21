import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# 從環境變數獲取加密金鑰 (ENCRYPTION_KEY)
# 如果沒有設定，則在啟動時拋出錯誤（生產環境必須設定）
_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

class SecretStorage:
    def __init__(self, key: str = None):
        if not key:
            key = _ENCRYPTION_KEY
        
        if not key:
            # 開發模式下自動生成一個（不建議，應使用 .env）
            print("⚠️ [WARNING] ENCRYPTION_KEY not found in .env. Using a temporary key.")
            key = Fernet.generate_key().decode()
            
        try:
            self.cipher = Fernet(key.encode())
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")

    def encrypt(self, plain_text: str) -> str:
        """加密字串"""
        if not plain_text:
            return ""
        return self.cipher.encrypt(plain_text.encode()).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """解密字串"""
        if not encrypted_text:
            return ""
        try:
            return self.cipher.decrypt(encrypted_text.encode()).decode()
        except Exception:
            return "DECRYPTION_ERROR"

# 全域單例
secret_manager = SecretStorage()

if __name__ == "__main__":
    # 測試腳本
    test_pwd = "my_app_password_123"
    enc = secret_manager.encrypt(test_pwd)
    dec = secret_manager.decrypt(enc)
    print(f"Original: {test_pwd}")
    print(f"Encrypted: {enc}")
    print(f"Decrypted: {dec}")
    assert test_pwd == dec
