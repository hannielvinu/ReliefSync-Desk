"""Pin the distributions installed and validated in the current environment."""

from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic-settings",
    "httpx",
    "aiosqlite",
    "rapidfuzz",
    "starlette",
    "anyio",
    "annotated-doc",
    "annotated-types",
    "pydantic-core",
    "typing-extensions",
    "typing-inspection",
    "python-dotenv",
    "opentelemetry-api",
    "h11",
    "httpcore",
    "certifi",
    "idna",
    "click",
]
DEV = [
    "pytest",
    "pytest-asyncio",
    "respx",
    "ruff",
    "pytest-cov",
    "coverage",
    "playwright",
    "pyee",
    "greenlet",
    "colorama",
    "iniconfig",
    "packaging",
    "pluggy",
    "pygments",
]


def main() -> None:
    (ROOT / "requirements.txt").write_text(
        "\n".join(f"{name}=={version(name)}" for name in RUNTIME) + "\n", encoding="utf-8"
    )
    (ROOT / "requirements-dev.txt").write_text(
        "-r requirements.txt\n" + "\n".join(f"{name}=={version(name)}" for name in DEV) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
