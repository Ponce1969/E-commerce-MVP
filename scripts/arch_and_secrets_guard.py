#!/usr/bin/env python3
"""Architecture & Secrets Guard for pre-commit and CI.

Enforces three non-negotiable engineering invariants:
1. Hexagonal Architecture Purity: `src/domain` must never import from `infrastructure`,
   `application`, `api`, `fastapi`, `sqlalchemy`, `httpx`, or `jwt`.
2. Zero Hardcoded Secrets/Tokens in Python (`backend/src`): AST inspection of sensitive
   identifiers (`*TOKEN*`, `*SECRET*`, `*PASSWORD*`, `*API_KEY*`) and Shannon entropy
   detection for high-entropy API keys.
3. Zero Hardcoded Credentials in Frontend DOM (`frontend/src/**/*.astro`): prevents
   `<input type="password" ... value="...">` from ever being committed.
"""

from __future__ import annotations

import ast
import math
import re
import sys
from pathlib import Path

FORBIDDEN_DOMAIN_IMPORTS = {
    "src.infrastructure",
    "src.application",
    "src.api",
    "fastapi",
    "sqlalchemy",
    "httpx",
    "jwt",
}

SENSITIVE_NAME_PATTERN = re.compile(
    r"(TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY|ACCESS_KEY)",
    re.IGNORECASE,
)

SAFE_DEV_PLACEHOLDERS = {
    "",
    "bearer",
    "postgres",
    "dev_secret_key_change_in_production",
    "!disabled_guest_account!",
    "password_reset",
    "access",
}

ASTRO_PASSWORD_VALUE_PATTERN = re.compile(
    r"<input\b[^>]*\btype\s*=\s*['\"]password['\"][^>]*\bvalue\s*=\s*['\"]([^'\"]+)['\"]"
    r"|<input\b[^>]*\bvalue\s*=\s*['\"]([^'\"]+)['\"][^>]*\btype\s*=\s*['\"]password['\"]",
    re.IGNORECASE,
)


def shannon_entropy(value: str) -> float:
    """Calculates Shannon entropy in bits per character."""
    if not value:
        return 0.0
    length = len(value)
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def is_likely_live_token(value: str) -> bool:
    """Detects high-entropy token strings (e.g. API keys, bearer tokens)."""
    stripped = value.strip()
    if len(stripped) < 28 or " " in stripped or "/" in stripped or ":" in stripped:
        return False
    # Must contain a mix of character classes (upper, lower, digits)
    has_upper = any(c.isupper() for c in stripped)
    has_lower = any(c.islower() for c in stripped)
    has_digit = any(c.isdigit() for c in stripped)
    if not (has_upper and has_lower and has_digit):
        return False
    return shannon_entropy(stripped) >= 4.0


def check_domain_hexagonal_purity(py_file: Path, tree: ast.AST) -> list[str]:
    """Ensures files inside `src/domain` never import outer framework or infrastructure layers."""
    errors: list[str] = []
    for node in ast.walk(tree):
        imported_modules: list[str] = []
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

        for mod in imported_modules:
            for forbidden in FORBIDDEN_DOMAIN_IMPORTS:
                if mod == forbidden or mod.startswith(f"{forbidden}."):
                    errors.append(
                        f"{py_file}:{getattr(node, 'lineno', 1)} [HEXAGONAL-VIOLATION] "
                        f"Domain layer cannot import '{mod}' (forbidden dependency: '{forbidden}')."
                    )
    return errors


def _extract_string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def check_python_hardcoded_secrets(py_file: Path, tree: ast.AST) -> list[str]:
    """Scans AST for hardcoded secrets/tokens assigned to sensitive variables or kwargs."""
    errors: list[str] = []

    for node in ast.walk(tree):
        pairs: list[tuple[str, str, int]] = []

        if isinstance(node, ast.Assign):
            val = _extract_string_constant(node.value)
            if val is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        pairs.append((target.id, val, node.lineno))
                    elif isinstance(target, ast.Attribute):
                        pairs.append((target.attr, val, node.lineno))

        elif isinstance(node, ast.AnnAssign):
            val = _extract_string_constant(node.value)
            if val is not None:
                if isinstance(node.target, ast.Name):
                    pairs.append((node.target.id, val, node.lineno))
                elif isinstance(node.target, ast.Attribute):
                    pairs.append((node.target.attr, val, node.lineno))

        elif isinstance(node, ast.keyword) and node.arg:
            val = _extract_string_constant(node.value)
            if val is not None:
                pairs.append((node.arg, val, getattr(node, "lineno", 1)))

        for name, raw_val, lineno in pairs:
            if SENSITIVE_NAME_PATTERN.search(name):
                if raw_val not in SAFE_DEV_PLACEHOLDERS:
                    errors.append(
                        f"{py_file}:{lineno} [HARDCODED-SECRET] "
                        f"Sensitive identifier '{name}' has a hardcoded literal value. "
                        f"Load from environment variables (.env) instead."
                    )
            elif is_likely_live_token(raw_val):
                errors.append(
                    f"{py_file}:{lineno} [HIGH-ENTROPY-TOKEN] "
                    f"Identifier '{name}' contains a high-entropy token string (len={len(raw_val)}, "
                    f"entropy={shannon_entropy(raw_val):.2f}). Move to environment variables."
                )

    return errors


def check_astro_dom_credentials(astro_file: Path) -> list[str]:
    """Checks .astro files for hardcoded password values in input fields."""
    errors: list[str] = []
    content = astro_file.read_text(encoding="utf-8", errors="ignore")
    for match in ASTRO_PASSWORD_VALUE_PATTERN.finditer(content):
        val = (match.group(1) or match.group(2) or "").strip()
        if val:
            lineno = content[: match.start()].count("\n") + 1
            errors.append(
                f"{astro_file}:{lineno} [DOM-CREDENTIAL-LEAK] "
                f"Password input field contains a non-empty hardcoded value attribute."
            )
    return errors


def scan_repository(root: Path) -> list[str]:
    """Runs all architecture and secret checks across the repository."""
    all_errors: list[str] = []

    backend_src = root / "backend" / "src"
    if backend_src.exists():
        for py_file in sorted(backend_src.rglob("*.py")):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError as exc:
                all_errors.append(f"{py_file}:{exc.lineno} [SYNTAX-ERROR] {exc.msg}")
                continue

            rel_parts = py_file.relative_to(backend_src).parts
            if rel_parts and rel_parts[0] == "domain":
                all_errors.extend(check_domain_hexagonal_purity(py_file, tree))

            all_errors.extend(check_python_hardcoded_secrets(py_file, tree))

    frontend_src = root / "frontend" / "src"
    if frontend_src.exists():
        for astro_file in sorted(frontend_src.rglob("*.astro")):
            all_errors.extend(check_astro_dom_credentials(astro_file))

    return all_errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    errors = scan_repository(repo_root)
    if errors:
        print("[FAIL] Architecture & Secrets Guard detected violations:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("[OK] Architecture & Secrets Guard passed (Hexagonal purity + Zero hardcoded secrets).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
