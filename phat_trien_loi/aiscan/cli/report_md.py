"""Dựng AISCAN-RESULTS.md từ các bản ghi trong thư mục chạy.

Trước đây bước này do model viết. Nhưng bản báo cáo chỉ trình bày lại những
con số đã có trong `findings.json`, `votes.json` và `coverage.json` — để model
viết là mở đường cho nó viết ra con số không khớp với dữ liệu. Dựng bằng mã
thì báo cáo luôn đúng bằng dữ liệu, và bớt được một lượt gọi.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiscan.lib import identity, strictjson
from aiscan.lib.strictjson import is_list, is_map

if TYPE_CHECKING:
    from pathlib import Path

SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def load(run_dir: Path, name: str) -> Any:
    """Một bản ghi trong thư mục chạy; None khi chưa có hoặc hỏng."""
    try:
        return strictjson.load(run_dir / name)
    except (OSError, ValueError):
        return None


def counted(findings: list[dict[str, Any]]) -> str:
    """Một dòng đếm finding theo mức nghiêm trọng."""
    tally = {level: 0 for level in SEVERITY_ORDER}
    for item in findings:
        level = str(item.get("severity", "")).upper()
        if level in tally:
            tally[level] += 1
    parts = [f"{count} {level}" for level, count in tally.items() if count]
    return ", ".join(parts) if parts else "không có finding nào"


def coverage_section(coverage: Any, meta: Any) -> list[str]:
    """Phần Coverage: quét cái gì, ở mức nào, bỏ sót cái gì."""
    lines = ["## Coverage", ""]
    effort = (coverage or {}).get("effort") if is_map(coverage) else None
    mode = (meta or {}).get("mode") if is_map(meta) else None
    root = (meta or {}).get("scan_root") if is_map(meta) else None
    lines.append(f"- Mục tiêu: `{root}`")
    lines.append(f"- Chế độ: `{mode}` · mức công: `{effort}`")

    if is_map(coverage):
        components = coverage.get("components")
        if is_list(components):
            names = {c.get("component") for c in components if is_map(c)}
            lines.append(f"- Component đã rà: {len(names)}")
        for key, label in (
            ("skippedComponents", "Khai báo bỏ qua"),
            ("droppedComponents", "Bị bỏ do vượt trần"),
            ("skippedLenses", "Lens bỏ qua"),
            ("sourceOmitted", "File không đưa được vào đề bài"),
        ):
            value = coverage.get(key)
            if is_list(value) and value:
                lines.append(f"- {label}: {len(value)}")
        notes = coverage.get("notes")
        if is_list(notes) and notes:
            lines.append("")
            lines.append("Ghi chú của lượt chạy:")
            lines += [f"- {note}" for note in notes[:20] if isinstance(note, str)]
    lines.append("")
    return lines


def finding_section(findings: list[dict[str, Any]], votes: Any) -> list[str]:
    """Phần Findings: mỗi finding một mục, kèm kết quả bỏ phiếu."""
    lines = ["## Findings", ""]
    if not findings:
        lines += ["Không có finding nào qua được hội đồng.", ""]
        return lines

    panels = {}
    if is_map(votes) and is_map(votes.get("panel")):
        panels = votes["panel"]

    for item in findings:
        finding_id = item.get("id", "?")
        severity = str(item.get("severity", "")).upper()
        confidence = str(item.get("confidence", "")).lower()
        title = item.get("title", "")
        lines.append(f"### {finding_id} — {title} ({severity}, confidence {confidence})")
        lines.append("")
        lines.append(f"`{item.get('file')}:{item.get('line')}` · {item.get('cwe_id')}")
        lines.append("")
        for label, key in (
            ("Vấn đề", "description"),
            ("Tác động", "impact"),
            ("Kịch bản khai thác", "exploit_scenario"),
            ("Khuyến nghị", "recommendation"),
        ):
            text = str(item.get(key) or "").strip()
            if text:
                lines.append(f"**{label}.** {text}")
                lines.append("")
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            lines.append("```")
            lines.append(snippet)
            lines.append("```")
            lines.append("")
        tally = panels.get(finding_id)
        if is_map(tally):
            lines.append(
                f"Hội đồng: {tally.get('true')}/{tally.get('voters')} phiếu thuận."
            )
            lines.append("")
    return lines


def verified_section(votes: Any, findings: list[dict[str, Any]]) -> list[str]:
    """Phần What was verified: con số chứng minh pipeline đã chạy."""
    lines = ["## What was verified", ""]
    if not is_map(votes):
        lines += ["Không có bản ghi phiếu bầu.", ""]
        return lines
    rows = [
        ("Ứng viên thô", votes.get("candidates")),
        ("Sau khử trùng lặp", votes.get("candidates_deduped")),
        ("Lượt nghiên cứu đã bắn", votes.get("researchers_dispatched")),
        ("Lượt nghiên cứu trả lời", votes.get("researchers_returned")),
        ("Tổng số phiếu", votes.get("panel_votes")),
        ("Ứng viên chưa xét", votes.get("unreviewed_candidate_sites")),
        ("Finding vào báo cáo", len(findings)),
    ]
    lines.append("| Chỉ số | Giá trị |")
    lines.append("| --- | ---: |")
    lines += [f"| {label} | {value} |" for label, value in rows if value is not None]
    lines.append("")
    chain = votes.get("chain")
    if is_map(chain) and (chain.get("pending") or chain.get("retry")):
        lines.append(
            f"Lượt chạy {chain.get('shard')} còn để lại phần chưa xác minh — "
            "chạy tiếp một lượt nữa để khép lại."
        )
        lines.append("")
    return lines


def build(run_dir: Path) -> str:
    """Toàn bộ báo cáo markdown cho lượt quét trong `run_dir`."""
    meta = load(run_dir, "scan-meta.json")
    coverage = load(run_dir, "coverage.json")
    votes = load(run_dir, "votes.json")
    raw = load(run_dir, "findings.json")
    findings = [f for f in raw if is_map(f)] if is_list(raw) else []

    head = [
        f"# {identity.NAME.upper()} results",
        "",
        f"Quét bằng {identity.NAME} v{identity.VERSION}. {counted(findings)}.",
        "",
    ]
    if is_map(meta):
        revision = meta.get("revision")
        if is_map(revision) and revision.get("commit"):
            dirty = " (working tree bẩn)" if revision.get("dirty") else ""
            head.append(f"Revision: `{revision['commit']}`{dirty}")
            head.append("")

    body = (
        head
        + coverage_section(coverage, meta)
        + finding_section(findings, votes)
        + verified_section(votes, findings)
        + [
            "## Rules",
            "",
            "Mỗi finding phải qua hội đồng ba giám khảo độc lập, mỗi người xét một",
            "lens (khả năng với tới, mức tác động, hàng phòng thủ sẵn có). Chỉ finding",
            "đủ ba phiếu và có ít nhất hai phiếu thuận mới vào báo cáo này. Mọi con số",
            "ở trên do mã nguồn đếm, không phải do model tự khai.",
            "",
        ]
    )
    return "\n".join(body)
