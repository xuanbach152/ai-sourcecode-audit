"""Các hằng số điều phối: lens chủ đề, lens xác minh, lượt sweep, mức công.

Mọi con số ở đây lấy từ `thiet_ke/thiet_ke.md` (mục đặc tả engine), tức trích
ngược từ engine gốc. Sửa ở đây thì sửa cả tài liệu đó.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Bốn lens chủ đề của giai đoạn nghiên cứu.
CATEGORIES = (
    (
        "injection-and-input",
        "injection and input handling: SQL/command/code injection, XSS, XXE, "
        "deserialization, template injection, ReDoS, path traversal from user input, "
        "prompt injection",
    ),
    (
        "auth-and-access",
        "authentication and authorization: auth bypass, missing or wrong authorization "
        "checks, IDOR, privilege escalation, CSRF, SSRF, open redirect, race conditions "
        "in access decisions",
    ),
    (
        "memory-and-unsafe",
        "memory and unsafe operations: buffer overflows, out-of-bounds access, "
        "use-after-free, integer overflow, type confusion, unsafe FFI, unchecked unsafe blocks",
    ),
    (
        "crypto-and-secrets",
        "cryptography and secrets: weak or misused crypto, weak randomness, key/nonce "
        "reuse, timing side channels, hardcoded secrets, credential handling and exposure",
    ),
)

# Ba lens của hội đồng xác minh: mỗi phiếu một lens.
PANEL_LENSES = ("REACHABILITY", "IMPACT", "DEFENSES")
PANEL_VOTERS = 3
PANEL_QUORUM = 2

# Ngôn ngữ có quản lý bộ nhớ: bỏ lens memory-and-unsafe cho component thuần các ngôn ngữ này.
MANAGED = re.compile(
    r"^(python|javascript|typescript|node(\.js)?|ruby|php|java|kotlin|scala|c#|csharp|"
    r"\.net|elixir|erlang|clojure|dart|perl|lua|r|shell|bash|sql|html|css)$",
    re.IGNORECASE,
)
JOINERS = re.compile(r"^(and|with|plus|or)$", re.IGNORECASE)
SPLIT = re.compile(r"[/,+&()\s]+")

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
SEVERITY_RANK = {name: len(SEVERITIES) - position for position, name in enumerate(SEVERITIES)}

# Khoảng 25 file mỗi component: đúng lượng một researcher đọc hết được.
FILES_PER_COMPONENT = 25
# Trần số mục trong một sổ độ phủ; dôi ra thì cắt.
ACCOUNT_CAP = 1000

SWEEPS = (
    (
        "sweep:1",
        True,
        "Look for entry points and dangerous sinks in files OUTSIDE the covered paths: "
        "scripts, configuration, CI definitions, migrations, admin tooling, glue code.",
    ),
    (
        "sweep:2",
        True,
        "Look for vulnerabilities that live BETWEEN components: a value validated in one "
        "and trusted in another, a boundary each side assumes the other checks, an "
        "inconsistent check across two paths to the same sink.",
    ),
)

SECRETS_SWEEP = (
    "sweep:secrets",
    False,
    "Look for hardcoded secrets, credentials, tokens, and private keys anywhere in the "
    "tree, including tests, fixtures, and configuration -- for this pass the fixtures ARE "
    "in scope, since a real key committed to a test file is a real leak.",
)


@dataclass(frozen=True)
class Effort:
    """Mức công quy ra các con số điều phối."""

    name: str
    component_cap: int
    repeats: int
    sweeps: int
    matrix: bool
    adversarial: bool


def effort_of(name: str, *, counted: bool = True) -> Effort:
    """Mức công `name`.

    `counted` là biết số file của mục tiêu quét hay không — write_scan_meta.py
    ghi con số đó vào scan-meta.json. Không biết thì trần component hạ xuống,
    vì không có gì để ước lượng số component hợp lý.
    """
    if name == "low":
        # Một component duy nhất cho cả repo, một lượt quét mọi lens cùng lúc.
        return Effort(name, component_cap=1, repeats=1, sweeps=0, matrix=False, adversarial=False)
    top = name in ("high", "max")
    cap = (48 if top else 24) if counted else (24 if top else 12)
    return Effort(
        name,
        component_cap=cap,
        repeats=2 if top else 1,
        sweeps=2 if top else 1,
        matrix=True,
        adversarial=name == "max",
    )


def words(language: str) -> list[str]:
    """Các từ ngôn ngữ trong `language`, bỏ các từ nối."""
    return [w for w in (p.strip() for p in SPLIT.split(language or "")) if w and not JOINERS.match(w)]


def categories_for(language: str) -> tuple[tuple[str, str], ...]:
    """Các lens áp cho một component; bỏ memory-and-unsafe với ngôn ngữ có quản lý bộ nhớ."""
    named = words(language)
    if named and all(MANAGED.match(w) for w in named):
        return tuple(c for c in CATEGORIES if c[0] != "memory-and-unsafe")
    return CATEGORIES


def sweeps_for(effort: Effort, *, secrets: bool) -> tuple[tuple[str, bool, str], ...]:
    """Các lượt sweep sẽ chạy ở mức công này."""
    passes = SWEEPS[: effort.sweeps]
    return (*passes, SECRETS_SWEEP) if secrets and effort.sweeps else passes
