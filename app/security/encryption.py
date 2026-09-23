from cryptography.fernet import Fernet

def generate_key() -> str:
    return Fernet.generate_key().decode()

def encrypt(value: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(value.encode()).decode()

def decrypt(value: str, key: str) -> str:
    return Fernet(key.encode()).decrypt(value.encode()).decode()
