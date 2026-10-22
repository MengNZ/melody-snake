"""Entry point: run the backend server (serves the built frontend too)."""

import uvicorn

from melody_snake.server import app


def main():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
