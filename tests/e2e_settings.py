"""Settings for tests/manual_e2e.py: real DB file, optional Laya server URL from environment."""
import os

from tests.settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "tests/test.db"}}
WAGTAIL_LAYA_URL = os.environ.get("WAGTAIL_LAYA_URL")
