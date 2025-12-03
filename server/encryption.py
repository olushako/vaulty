from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

from .config import MASTER_KEY


def derive_key(master_key: bytes) -> bytes:
    """Derive a Fernet key from the master key"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'vaulty_salt_2024',  # Fixed salt for consistency
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_key))
    return key


# Initialize Fernet with derived key
_fernet = Fernet(derive_key(MASTER_KEY))


def encrypt_data(data: str) -> bytes:
    """Encrypt string data"""
    return _fernet.encrypt(data.encode('utf-8'))


def decrypt_data(encrypted_data: bytes) -> str:
    """Decrypt encrypted data to string"""
    return _fernet.decrypt(encrypted_data).decode('utf-8')




