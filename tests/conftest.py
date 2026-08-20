import os

import pytest
from cachelib import SimpleCache

from app import Config, create_app
from app.pda.mock_api import MockProviderDataApi


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {
            "width": 1920,
            "height": 1080,
        },
    }


class TestConfig(Config):
    TESTING = True
    PROPAGATE_EXCEPTIONS = False
    DEBUG = True
    SECRET_KEY = "TEST_KEY"
    PDA_URL = "http://mock-api.test"
    PDA_API_KEY = "test-key"
    SERVER_NAME = "localhost"
    PREFERRED_URL_SCHEME = "http"
    SKIP_AUTH = True
    # Use in-memory cache for testing sessions
    SESSION_TYPE = "cachelib"
    SESSION_CACHELIB = SimpleCache()
    RATELIMIT_ENABLED = False
    # Use memory storage for rate limiting in tests
    RATELIMIT_STORAGE_URI = "memory://"
    WTF_CSRF_ENABLED = False


@pytest.fixture(scope="session")
def app(config=TestConfig):
    use_real_pda = os.environ.get("TEST_USE_REAL_PDA", "false").lower() == "true"

    if use_real_pda:

        class RealPdaTestConfig(TestConfig):
            PDA_USE_MOCK_API = False
            PDA_URL = os.environ.get("TEST_PDA_URL", os.environ.get("PDA_URL", "http://localhost:8080"))
            PDA_API_KEY = os.environ.get("TEST_PDA_API_KEY", os.environ.get("PDA_API_KEY", "Dummy1"))

        app = create_app(RealPdaTestConfig)
    else:
        app = create_app(config, MockProviderDataApi)

    with app.app_context():
        yield app
