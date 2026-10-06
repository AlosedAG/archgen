"""Shared pytest setup: skip the login gate (core.auth) so AppTest can load
Home.py without secrets. Login itself is covered in test_auth.py."""

import os

os.environ.setdefault("AUTH_DISABLED", "1")
