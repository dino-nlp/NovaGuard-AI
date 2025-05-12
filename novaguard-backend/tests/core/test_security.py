import unittest
from datetime import timedelta, datetime, timezone
from time import sleep

from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
    SECRET_KEY, # Import để có thể dùng trong test nếu cần, nhưng thường không nên expose
    ALGORITHM
)
from app.core.config import settings # Để truy cập ACCESS_TOKEN_EXPIRE_MINUTES

# Để tránh lỗi SECRET_KEY quá ngắn hoặc không an toàn trong môi trường test,
# chúng ta có thể ghi đè nó nếu cần, hoặc đảm bảo settings.SECRET_KEY đủ mạnh.
# For testing, ensure a valid key is used if the default placeholder is too weak for 'python-jose'
if settings.SECRET_KEY == "your-super-secret-key-please-change-this":
    # This is a known weak key, python-jose might complain.
    # For robust testing, consider mocking settings.SECRET_KEY or using a dedicated test key.
    # However, for this example, we'll proceed assuming it works for basic encoding/decoding.
    pass


class TestSecurity(unittest.TestCase):

    def test_password_hashing_and_verification(self):
        password = "testpassword123"
        hashed_password = get_password_hash(password)

        self.assertNotEqual(password, hashed_password)
        self.assertTrue(verify_password(password, hashed_password))
        self.assertFalse(verify_password("wrongpassword", hashed_password))

    def test_create_and_decode_access_token(self):
        subject = "testuser@example.com"
        token = create_access_token(subject)
        self.assertIsInstance(token, str)

        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("sub"), subject)
        
        # Check expiration time is roughly correct
        expected_exp_min = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES -1) # allow 1 min diff
        expected_exp_max = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES +1)
        
        token_exp_timestamp = payload.get("exp")
        self.assertIsNotNone(token_exp_timestamp)
        token_exp_datetime = datetime.fromtimestamp(token_exp_timestamp, timezone.utc)
        
        self.assertTrue(expected_exp_min < token_exp_datetime < expected_exp_max)


    def test_decode_invalid_token(self):
        invalid_token = "this.is.not.a.valid.token"
        payload = decode_access_token(invalid_token)
        self.assertIsNone(payload)

    def test_decode_expired_token(self):
        subject = "expireduser@example.com"
        # Create a token that expired 1 second ago
        expired_token = create_access_token(subject, expires_delta=timedelta(seconds=-1))
        
        # Wait a tiny bit to ensure it's definitely expired if system clocks are slightly off
        # sleep(0.1) # Usually not needed if delta is clearly negative

        payload = decode_access_token(expired_token)
        self.assertIsNone(payload, "Expired token should not be decodable to a valid payload.")

    def test_custom_expiration_delta(self):
        subject = "customexp@example.com"
        custom_delta = timedelta(hours=2)
        token = create_access_token(subject, expires_delta=custom_delta)
        
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        
        expected_exp_min = datetime.now(timezone.utc) + custom_delta - timedelta(minutes=1)
        expected_exp_max = datetime.now(timezone.utc) + custom_delta + timedelta(minutes=1)
        
        token_exp_timestamp = payload.get("exp")
        self.assertIsNotNone(token_exp_timestamp)
        token_exp_datetime = datetime.fromtimestamp(token_exp_timestamp, timezone.utc)
        
        self.assertTrue(expected_exp_min < token_exp_datetime < expected_exp_max)

if __name__ == '__main__':
    unittest.main()