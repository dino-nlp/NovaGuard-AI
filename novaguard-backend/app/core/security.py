from datetime import datetime, timedelta, timezone
from typing import Any, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings # Import settings từ config.py

# --- Password Hashing ---
# Sử dụng CryptContext để quản lý việc hash password.
# "bcrypt" là một thuật toán hashing mạnh và phổ biến.
# deprecated="auto" sẽ tự động xử lý các hash cũ nếu bạn thay đổi thuật toán trong tương lai.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Xác minh mật khẩu thuần túy với mật khẩu đã được hash.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Tạo hash từ mật khẩu thuần túy.
    """
    return pwd_context.hash(password)


# --- JSON Web Tokens (JWT) ---
ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY # Lấy từ config
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(subject: Union[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Tạo một access token mới.
    :param subject: Dữ liệu để mã hóa vào token (thường là user ID hoặc email).
    :param expires_delta: Thời gian token sẽ hết hạn. Nếu None, sử dụng giá trị mặc định.
    :return: Chuỗi JWT.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict | None:
    """
    Giải mã access token.
    Trả về payload nếu token hợp lệ và chưa hết hạn, ngược lại trả về None.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError: # Bao gồm cả ExpiredSignatureError và các lỗi JWT khác
        return None

if __name__ == '__main__':
    # Ví dụ sử dụng (chỉ để test)
    plain_pw = "mysecretpassword"
    hashed_pw = get_password_hash(plain_pw)
    print(f"Plain password: {plain_pw}")
    print(f"Hashed password: {hashed_pw}")
    print(f"Verification (correct): {verify_password(plain_pw, hashed_pw)}")
    print(f"Verification (incorrect): {verify_password('wrongpassword', hashed_pw)}")

    print("-" * 20)
    # Test JWT
    user_identifier = "user@example.com"
    token = create_access_token(user_identifier)
    print(f"Generated JWT for '{user_identifier}': {token}")
    
    # Test decoding
    payload = decode_access_token(token)
    if payload:
        print(f"Decoded payload: {payload}")
        print(f"Subject (sub): {payload.get('sub')}")
        exp_timestamp = payload.get('exp')
        if exp_timestamp:
            print(f"Expires at (UTC): {datetime.fromtimestamp(exp_timestamp, timezone.utc)}")
    else:
        print("Failed to decode token or token is invalid/expired.")

    # Test expired token
    expired_token = create_access_token(user_identifier, expires_delta=timedelta(seconds=-1))
    print(f"Generated expired JWT: {expired_token}")
    payload_expired = decode_access_token(expired_token)
    if payload_expired:
        print(f"Decoded expired payload (should not happen): {payload_expired}")
    else:
        print("Correctly failed to decode expired token.")