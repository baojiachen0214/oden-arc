"""One allowlist for public source audits and source archives.

This is deliberately not a publisher, a Git-history exporter or a credential
scanner with an exhaustive signature database. Keep real workspaces elsewhere.
"""
from __future__ import annotations

from pathlib import Path

ARCHIVE_ROOT = "oden-arc"
DIRECTORIES = {
    ".github", "agents", "assets", "docs", "examples", "prompts", "references",
    "schemas", "scripts", "src", "tests",
}
ROOT_FILES = {
    "README.md", "README.zh-CN.md", "README.zh-TW.md", "SKILL.md", "AGENTS.md",
    "LICENSE", "NOTICE.md", "THIRD_PARTY.md", "CONTRIBUTING.md", "SECURITY.md",
    "CHANGELOG.md", "pyproject.toml", ".gitignore", ".gitattributes", ".editorconfig",
    "requirements-media.txt", "requirements-dev.txt", "MANIFEST.in",
}
IGNORED = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", "build", "dist", "htmlcov",
}
REQUIRED = {
    "README.md", "README.zh-CN.md", "README.zh-TW.md", "SKILL.md", "LICENSE",
    "CONTRIBUTING.md", "SECURITY.md", "THIRD_PARTY.md", "pyproject.toml",
    "src/oden_arc/native.py", "src/oden_arc/export_layout.py", "src/oden_arc/memory.py",
    "src/oden_arc/atlas.py", "src/oden_arc/evidence_gate.py", "src/oden_arc/media.py",
    "prompts/02-extract-batch.md", "references/context-atlas.md",
    "schemas/map-plan.schema.json", "tests/test_memory.py", "tests/test_atlas.py",
    "tests/test_evidence_gate.py", "tests/test_public.py", "scripts/audit_public.py",
    "examples/quickstart/plan.json", "docs/releasing.md", "assets/brand/README.md",
    "assets/brand/logo.png", ".github/workflows/ci.yml",
}


def ignored(relative: Path) -> bool:
    return any(part in IGNORED or part.endswith('.egg-info') for part in relative.parts)


def selected_files(root: Path) -> list[Path]:
    """Fail on symlinks; select only explicitly approved public directories."""
    result = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink is not allowed in a source release: {relative}")
        if not path.is_file() or path.suffix in {'.pyc', '.pyo'}:
            continue
        allowed = (len(relative.parts) == 1 and path.name in ROOT_FILES) or (
            len(relative.parts) > 1 and relative.parts[0] in DIRECTORIES
        )
        if allowed:
            result.append(path)
    return result


def selected_directories(root: Path) -> list[str]:
    result = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if ignored(relative) or relative.parts[0] not in DIRECTORIES:
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink is not allowed: {relative}")
        if path.is_dir():
            result.append(relative.as_posix())
    return result
