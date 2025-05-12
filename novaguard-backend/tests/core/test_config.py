import unittest
from unittest.mock import patch
import os

from app.core.config import Settings, get_settings # Đảm bảo PYTHONPATH đúng

class TestSettings(unittest.TestCase):

    def test_default_settings_loaded(self):
        """Test if default settings are loaded correctly."""
        settings = Settings()
        self.assertEqual(settings.DATABASE_URL, "postgresql://novaguard_user:novaguard_password@postgres_db:5432/novaguard_db")
        self.assertEqual(settings.ALGORITHM, "HS256")
        self.assertEqual(settings.ACCESS_TOKEN_EXPIRE_MINUTES, 60 * 24)
        self.assertIn("your-super-secret-key", settings.SECRET_KEY) # Check default placeholder

    @patch.dict(os.environ, {
        "DATABASE_URL": "env_db_url",
        "SECRET_KEY": "env_secret_key",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "OLLAMA_BASE_URL": "http://env_ollama_url"
    })
    def test_settings_loaded_from_env(self):
        """Test if settings are correctly overridden by environment variables."""
        # Clear lru_cache for get_settings to re-evaluate
        get_settings.cache_clear()
        settings = get_settings()

        self.assertEqual(settings.DATABASE_URL, "env_db_url")
        self.assertEqual(settings.SECRET_KEY, "env_secret_key")
        self.assertEqual(settings.ACCESS_TOKEN_EXPIRE_MINUTES, 30)
        self.assertEqual(settings.OLLAMA_BASE_URL, "http://env_ollama_url")

        # Clean up cache again for other tests
        get_settings.cache_clear()

    def test_settings_are_cached(self):
        """Test that get_settings() returns a cached instance."""
        get_settings.cache_clear() # Ensure clean state
        s1 = get_settings()
        s2 = get_settings()
        self.assertIs(s1, s2)
        get_settings.cache_clear() # Clean up

if __name__ == '__main__':
    unittest.main()