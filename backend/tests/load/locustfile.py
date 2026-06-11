"""Load profile for the go-live soak test.

Drives the endpoints a live event hammers hardest: login, catalogue
browse, scoreboard, and flag submission (wrong flag — the failure
path runs the full dispatch + audit pipeline without mutating
scores).

Not part of the pytest suite — run it against a *staging* stack:

    pip install locust
    locust -f backend/tests/load/locustfile.py \
        --host http://localhost:8080 \
        -u 50 -r 5 --run-time 10m

Pass ``LOAD_TEST_PASSWORD`` if the seeded load users use a
different password (users are self-registered on first request, so
a fresh staging stack needs no preparation).

Watch while it runs (docs/alerts thresholds):
  * p99 latency < 1s on /api/v1/challenges and /api/v1/scoreboard
  * zero 5xx — 409/429 are expected and counted as success below
  * flat memory on the api container (docker stats)
"""

from __future__ import annotations

import os
import random
import string

from locust import HttpUser, between, task

_PASSWORD = os.environ.get("LOAD_TEST_PASSWORD", "LoadTestPassw0rd!")


def _rand_suffix(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


class Player(HttpUser):
    wait_time = between(1, 4)

    def on_start(self) -> None:
        suffix = _rand_suffix()
        self.email = f"load-{suffix}@load.local"
        self.username = f"load-{suffix}"
        r = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "username": self.username,
                "password": _PASSWORD,
            },
            name="/api/v1/auth/register",
        )
        if r.status_code == 201:
            self.token = r.json()["access_token"]
        else:
            login = self.client.post(
                "/api/v1/auth/login",
                json={"email": self.email, "password": _PASSWORD},
                name="/api/v1/auth/login",
            )
            self.token = login.json().get("access_token", "")
        self.client.headers["Authorization"] = f"Bearer {self.token}"
        self.slugs: list[str] = []

    @task(5)
    def browse_challenges(self) -> None:
        r = self.client.get("/api/v1/challenges", name="/api/v1/challenges")
        if r.ok:
            items = r.json().get("items") or r.json().get("data") or []
            self.slugs = [
                c.get("slug") for c in items if isinstance(c, dict) and c.get("slug")
            ]

    @task(3)
    def scoreboard(self) -> None:
        self.client.get("/api/v1/scoreboard", name="/api/v1/scoreboard")

    @task(2)
    def me(self) -> None:
        self.client.get("/api/v1/me", name="/api/v1/me")

    @task(2)
    def submit_wrong_flag(self) -> None:
        if not self.slugs:
            return
        slug = random.choice(self.slugs)
        # Wrong flag on purpose: exercises dispatch + audit + rate
        # limiting without corrupting the scoreboard. 200 (incorrect),
        # 409 (already solved) and 429 (rate limited) are all healthy.
        with self.client.post(
            f"/api/v1/challenges/{slug}/submit",
            json={"flag": f"CTF{{load-test-{_rand_suffix()}}}"},
            name="/api/v1/challenges/[slug]/submit",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 400, 404, 409, 412, 429):
                r.success()
            else:
                r.failure(f"unexpected status {r.status_code}")
