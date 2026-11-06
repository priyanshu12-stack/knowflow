"""Fail if a paid / hosted inference SDK or endpoint enters the codebase (TRD §1, ADR-007).

Checks dependency manifests and source files. Run: python scripts/check_no_paid_apis.py
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED_PACKAGES = {
    # Python
    "openai",
    "anthropic",
    "google-generativeai",
    "google-genai",
    "cohere",
    "mistralai",
    "groq",
    "together",
    "replicate",
    "voyageai",
    "langchain-openai",
    "langchain-anthropic",
    "langchain-google-genai",
    "llama-index-llms-openai",
    # JavaScript
    "@anthropic-ai/sdk",
    "@google/generative-ai",
    "@google/genai",
    "@mistralai/mistralai",
    "@ai-sdk/openai",
    "@ai-sdk/anthropic",
    "@ai-sdk/google",
    "cohere-ai",
    "groq-sdk",
}

BANNED_HOSTS = re.compile(
    r"api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com"
    r"|api\.cohere\.(ai|com)|api\.mistral\.ai|api\.groq\.com|api\.together\.xyz"
    r"|api\.replicate\.com|api\.voyageai\.com"
)

SOURCE_GLOBS = ["apps/api/app/**/*.py", "apps/web/src/**/*.ts", "apps/web/src/**/*.tsx"]


def _normalise(name: str) -> str:
    return re.split(r"[\s<>=!~;\[]", name.strip(), maxsplit=1)[0].lower().replace("_", "-")


def python_deps() -> set[str]:
    data = tomllib.loads((ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8"))
    project = data.get("project", {})
    deps = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        deps.extend(group)
    return {_normalise(d) for d in deps}


def js_deps() -> set[str]:
    pkg = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    return {
        name.lower()
        for section in ("dependencies", "devDependencies", "optionalDependencies")
        for name in pkg.get(section, {})
    }


def main() -> int:
    problems = [
        f"banned dependency: {d}" for d in sorted((python_deps() | js_deps()) & BANNED_PACKAGES)
    ]
    for pattern in SOURCE_GLOBS:
        for path in ROOT.glob(pattern):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if BANNED_HOSTS.search(line):
                    problems.append(f"paid inference endpoint: {path.relative_to(ROOT)}:{lineno}")
    if problems:
        print("Zero-paid-API policy violated (see docs/decisions/ADR-007):")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    print("OK: no paid inference SDKs or endpoints found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
