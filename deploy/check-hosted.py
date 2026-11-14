"""Smoke-test the disposable hosted image; never point this at a live service."""

import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:10000"


def login(password):
    request = urllib.request.Request(
        BASE + "/api/v1/auth/login",
        data=json.dumps({"email": "owner@example.com", "password": password}).encode(),
        headers={"Content-Type": "application/json", "Origin": "https://localhost"},
    )
    try:
        return urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as error:
        return error


for _ in range(60):
    try:
        with urllib.request.urlopen(BASE + "/api/v1/health", timeout=5) as response:
            assert json.load(response)["status"] == "ok"
        break
    except (OSError, AssertionError):
        time.sleep(2)
else:
    raise SystemExit("Hosted image did not become healthy")

with urllib.request.urlopen(BASE + "/login", timeout=30) as response:
    html = response.read().decode()
    assert "concord-demo-2026" not in html
    assert "EXPLORE THE DEMO" not in html

response = login("hosted-test-password-2026")
assert response.status == 200, response.status
assert "Secure" in response.headers["Set-Cookie"]
assert "HttpOnly" in response.headers["Set-Cookie"]
assert json.load(response)["user"]["role"] == "admin"
for _ in range(9):
    assert login("incorrect-password").status == 401
response = login("incorrect-password")
assert response.status == 429
assert int(response.headers["Retry-After"]) > 0
print("PASS: hosted health, empty login, real admin, secure cookies, persisted 429 rate limit")
