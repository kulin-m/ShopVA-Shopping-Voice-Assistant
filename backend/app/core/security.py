import hashlib
import hmac
import base64
import json
import time
from typing import Optional, Dict, Any
from app.core.config import settings

def hash_password(password: str) -> str:
    """Hashes password using SHA256 with HMAC secret key salt."""
    salt = settings.SECRET_KEY.encode('utf-8')
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return base64.b64encode(key).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against hashed password."""
    try:
        expected = hash_password(plain_password)
        return hmac.compare_digest(expected, hashed_password)
    except Exception:
        return False

def create_access_token(payload: Dict[str, Any], expires_in_seconds: int = 86400 * 7) -> str:
    """Generates signed JWT access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_bytes = base64.urlsafe_b64encode(json.dumps(header).encode('utf-8')).rstrip(b'=')
    
    payload_copy = payload.copy()
    payload_copy["exp"] = int(time.time()) + expires_in_seconds
    payload_copy["iat"] = int(time.time())
    payload_bytes = base64.urlsafe_b64encode(json.dumps(payload_copy).encode('utf-8')).rstrip(b'=')
    
    signing_input = header_bytes + b'.' + payload_bytes
    signature = hmac.new(settings.SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_bytes = base64.urlsafe_b64encode(signature).rstrip(b'=')
    
    return (signing_input + b'.' + sig_bytes).decode('utf-8')

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates signed JWT access token signature and expiration."""
    try:
        parts = token.strip().split('.')
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, sig_b64 = parts
        signing_input = (header_b64 + '.' + payload_b64).encode('utf-8')
        
        expected_sig = hmac.new(settings.SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b'=').decode('utf-8')
        
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None
        
        # Add padding back if missing for b64decode
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += '=' * (4 - rem)
        
        payload_data = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
        
        # Check expiration
        exp = payload_data.get("exp")
        if exp and time.time() > exp:
            return None
            
        return payload_data
    except Exception:
        return None
