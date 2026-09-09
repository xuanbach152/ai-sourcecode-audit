"""Đo chi phí một lượt quét: thời gian, số token, và log từng lượt gọi.

Đây là số liệu cho báo cáo so sánh với Fortify: thời gian quét và chi phí
token. Token lấy từ cổng khi cổng trả về `usage`; không có thì ước lượng theo
độ dài văn bản và **đánh dấu rõ là ước lượng** — một con số ước lượng bị nhầm
thành số đo thật sẽ làm hỏng cả bảng so sánh.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# Ước lượng thô khi cổng không trả usage: 4 ký tự một token.
CHARS_PER_TOKEN = 4

# Các tên trường mà cổng tương thích OpenAI hay dùng cho số token.
INPUT_KEYS = ("prompt_tokens", "input_tokens", "inputTokens", "promptTokens")
OUTPUT_KEYS = ("completion_tokens", "output_tokens", "outputTokens", "completionTokens")

UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def estimate(text: str) -> int:
    """Số token ước lượng của `text`."""
    return max(1, len(text) // CHARS_PER_TOKEN) if text else 0


def find_usage(payload: object, found: dict[str, int]) -> None:
    """Gom số token từ bất kỳ khối `usage` nào lồng trong `payload`.

    Đi đệ quy vì mỗi phiên bản Codev lồng usage ở một độ sâu khác nhau; cộng
    dồn thay vì lấy cái đầu tiên, vì một lượt agent có thể gồm nhiều request.
    """
    if isinstance(payload, list):
        for item in payload:
            find_usage(item, found)
        return
    if not isinstance(payload, dict):
        return
    # Codev: part.tokens = {input, output, reasoning, total, cache{...}}.
    # Token suy luan la token duoc sinh ra, nen tinh vao dau ra.
    block = payload.get("tokens")
    if isinstance(block, dict):
        for key, name in (("input", "input"), ("output", "output"), ("reasoning", "output")):
            value = block.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                found[name] = found.get(name, 0) + value

    for keys, name in ((INPUT_KEYS, "input"), (OUTPUT_KEYS, "output")):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                found[name] = found.get(name, 0) + value
                break
    for value in payload.values():
        if isinstance(value, (dict, list)):
            find_usage(value, found)


def usage_of(payload: object) -> tuple[int, int] | None:
    """`(token vào, token ra)` cổng báo, hoặc None khi cổng không báo."""
    found: dict[str, int] = {}
    find_usage(payload, found)
    if not found:
        return None
    return found.get("input", 0), found.get("output", 0)


def slug(text: str) -> str:
    """`text` rút thành tên file an toàn."""
    return UNSAFE.sub("-", text).strip("-")[:60] or "call"


@dataclass
class Call:
    """Một lượt gọi agent đã đo."""

    index: int
    phase: str
    agent: str
    label: str
    seconds: float
    tokens_in: int
    tokens_out: int
    estimated: bool
    ok: bool
    error: str = ""

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass
class Metrics:
    """Sổ đo của cả lượt quét."""

    calls: list[Call] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)

    def record(self, call: Call) -> None:
        self.calls.append(call)

    @property
    def elapsed(self) -> float:
        """Thời gian trôi qua từ lúc bắt đầu lượt quét, tính cả phần chạy song song."""
        return time.monotonic() - self.started

    def phases(self) -> list[str]:
        """Tên các giai đoạn, theo thứ tự xuất hiện."""
        return list(dict.fromkeys(call.phase for call in self.calls))

    def summary(self) -> list[dict[str, Any]]:
        """Tổng hợp theo giai đoạn, cộng một dòng tổng cuối."""
        rows = []
        for phase in self.phases():
            rows.append(self.totals(phase, [c for c in self.calls if c.phase == phase]))
        rows.append(self.totals("TỔNG", self.calls))
        return rows

    @staticmethod
    def totals(name: str, calls: Sequence[Call]) -> dict[str, Any]:
        """Một dòng tổng hợp cho `calls`."""
        return {
            "phase": name,
            "calls": len(calls),
            "failed": sum(not c.ok for c in calls),
            # Cộng thời gian từng lượt: đây là tổng công, không phải thời gian
            # thực tế trôi qua, vì các lượt chạy song song.
            "seconds": round(sum(c.seconds for c in calls), 1),
            "tokens_in": sum(c.tokens_in for c in calls),
            "tokens_out": sum(c.tokens_out for c in calls),
            "estimated": any(c.estimated for c in calls),
        }

    def to_dict(self, *, budget: int | None = None) -> dict[str, Any]:
        """Toàn bộ sổ đo dưới dạng JSON."""
        total = self.totals("TỔNG", self.calls)
        record: dict[str, Any] = {
            "wall_seconds": round(self.elapsed, 1),
            "agent_seconds": total["seconds"],
            "calls": total["calls"],
            "failed_calls": total["failed"],
            "tokens_in": total["tokens_in"],
            "tokens_out": total["tokens_out"],
            "tokens_total": total["tokens_in"] + total["tokens_out"],
            "tokens_estimated": total["estimated"],
            "by_phase": self.summary(),
            "per_call": [vars(c) for c in self.calls],
        }
        if budget:
            record["token_budget"] = budget
            record["token_budget_used_pct"] = round(
                100 * record["tokens_total"] / budget, 3
            )
        return record

    def table(self, *, budget: int | None = None) -> str:
        """Bảng tổng hợp để in ra cuối lượt quét."""
        head = f"{'GIAI DOAN':<16}{'LUOT':>6}{'LOI':>5}{'THOI GIAN':>12}{'TOKEN VAO':>12}{'TOKEN RA':>11}"
        lines = [head, "-" * len(head)]
        for row in self.summary():
            if row["phase"] == "TỔNG":
                lines.append("-" * len(head))
            lines.append(
                f"{row['phase']:<16}{row['calls']:>6}{row['failed']:>5}"
                f"{row['seconds']:>11.1f}s{row['tokens_in']:>12,}{row['tokens_out']:>11,}"
            )
        total = self.totals("TỔNG", self.calls)
        lines.append("")
        lines.append(f"Thoi gian thuc te troi qua: {self.elapsed:.1f}s (cac luot chay song song)")
        if total["estimated"]:
            lines.append("! Co luot khong duoc cong bao token: so lieu la UOC LUONG.")
        if budget:
            used = total["tokens_in"] + total["tokens_out"]
            lines.append(f"Han muc token: {used:,} / {budget:,} ({100 * used / budget:.3f}%)")
        return "\n".join(lines)


def transcript(call: Call, message: str, stdout: str, answer: object) -> dict[str, Any]:
    """Bản ghi đầy đủ một lượt gọi, để soi khi model trả lời sai."""
    return {
        "index": call.index,
        "phase": call.phase,
        "agent": call.agent,
        "label": call.label,
        "seconds": call.seconds,
        "tokens_in": call.tokens_in,
        "tokens_out": call.tokens_out,
        "tokens_estimated": call.estimated,
        "ok": call.ok,
        "error": call.error,
        "message": message,
        "stdout": stdout,
        "answer": answer,
    }


def names(calls: Iterable[Call]) -> list[str]:
    """Tên file log cho từng lượt, đánh số để giữ thứ tự."""
    return [f"{call.index:03d}-{slug(call.label)}.json" for call in calls]
