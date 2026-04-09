from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version


def get_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not installed"


def main() -> None:
    print(f"Python: {platform.python_version()}")
    for package in [
        "langgraph",
        "langchain-core",
        "langchain-openai",
        "openai",
        "pydantic",
        "python-dotenv",
    ]:
        print(f"{package}: {get_version(package)}")


if __name__ == "__main__":
    main()
