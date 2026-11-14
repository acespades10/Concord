"""Run the API and web proxy in one free-tier container, without demo seeding."""

import os
import signal
import subprocess
import sys
import time


def main():
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "app.bootstrap"], check=True)
    children = []

    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(
            subprocess.Popen(["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
        )
        children.append(
            subprocess.Popen(
                ["node", "/app/web/apps/web/server.js"],
                env={**os.environ, "HOSTNAME": "0.0.0.0", "PORT": os.environ.get("PORT", "10000")},
            )
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    sys.exit(next((child.returncode for child in children if child.returncode), 0))


if __name__ == "__main__":
    main()
