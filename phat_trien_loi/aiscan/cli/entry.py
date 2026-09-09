"""Bảng chọn khởi động AIScan — `run.py` gọi main() ở đây.

    python run.py                  banner, hỏi repo, hỏi chế độ, hỏi mức công
    python run.py <repo>           banner và bảng chọn cho repo đó
    python run.py scan <repo>      quét thẳng code-base, không hỏi
    python run.py banner           chỉ in banner, rồi dừng (màu ở terminal thật; --color ép, --no-color tắt)

Chỉ chế độ code-base có pipeline; hai chế độ còn lại in thông báo rồi quay lại
bảng chọn. Các cờ thừa (như --out, --workers) được chuyển nguyên sang lượt quét.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aiscan.lib import banner, console

from . import scan

EFFORTS = ("low", "medium", "high", "max")

# (phím, tên, dòng mô tả chính, dòng phụ — rỗng nếu không cần)
MODES = (
    ("1", "code-base", "Quét cả repository (mặc định)",
     "7 giai đoạn · báo cáo + SARIF"),
    ("2", "changes", "Quét thay đổi của nhánh/commit", ""),
    ("3", "patch", "Đề xuất patch từ finding của báo cáo", ""),
)

NOT_READY = {
    "changes": (
        "Pipeline chưa tính diff — merge-base, numstat, chỉ đọc các file đổi.",
        "Chọn 1 (code-base), hoặc đợi bản sau.",
    ),
    "patch": (
        "Cần điều phối patch-generator/patch-verifier và một báo cáo có finding.",
        "Chọn 1 (code-base), hoặc đợi bản sau.",
    ),
}

WIDTH = 58


def _painter(color: bool):
    """Hàm tô màu theo ngữ cảnh; không tô khi đầu ra không phải terminal."""

    def paint(text: str, code: str = "") -> str:
        return f"{code}{text}{banner.RESET}" if color and code else text

    return paint


def render_menu(repo: str, *, color: bool) -> str:
    paint = _painter(color)
    rule = paint("─" * WIDTH, banner.GREY)
    lines = [
        rule,
        paint("  CHỌN CHẾ ĐỘ QUÉT", banner.BOLD),
        paint(f"  repo  {repo}", banner.GREY),
        "",
    ]
    for key, name, main, extra in MODES:
        ready = name == "code-base"
        badge = "" if ready else paint("  — sắp có", banner.GREY)
        label = paint(f"{name:<10}", banner.BOLD)
        lines.append(f"  {paint(key, banner.ACCENT)}  {label}  {main}{badge}")
        if extra:
            lines.append(f"  {' ':<3}{'':<10}  {paint(extra, banner.GREY)}")
    lines.append(
        f"  {paint('q', banner.ACCENT)}  {paint('thoát', banner.GREY)}")
    lines.append(rule)
    return "\n".join(lines)


def render_notice(name: str, detail: tuple[str, str], *, color: bool) -> str:
    paint = _painter(color)
    rule = paint("═" * WIDTH, banner.GREY)
    return "\n".join(
        (
            rule,
            f" {paint('▸', banner.ACCENT)} {paint(name.upper(), banner.BOLD)}"
            f" {paint('— chưa có trong bản này', banner.GREY)}",
            f"   {detail[0]}",
            paint(f"   {detail[1]}", banner.GREY),
            rule,
        )
    )


def render_effort_prompt(*, color: bool) -> str:
    paint = _painter(color)
    choices = " · ".join(
        e if e == "low" else paint(e, banner.ACCENT) for e in EFFORTS
    )
    return f"Mức cố gắng ({choices})  [Enter = low] — cao hơn = rà kỹ hơn, tốn token hơn: "


def usage() -> int:
    banner.emit()
    print()
    print("Dùng:")
    print("  python run.py                  banner, hỏi repo, hỏi chế độ, hỏi mức cố gắng")
    print("  python run.py <repo>           banner và bảng chọn cho repo đó")
    print("  python run.py scan <repo>      quét thẳng code-base, không hỏi")
    print("  python run.py banner           chỉ in banner, rồi dừng (màu ở terminal thật; --color ép, --no-color tắt)")
    print("  python run.py <repo> --effort low|medium|high|max   bỏ qua câu hỏi mức cố gắng")
    print()
    print("Chế độ:")
    for key, name, main, _ in MODES:
        ready = "" if name == "code-base" else "  (chưa có — chỉ thông báo)"
        print(f"  [{key}] {name:<10} {main}{ready}")
    return 0


def ask_repo() -> str | None:
    """Hỏi đường dẫn repo đến khi hợp lệ; None khi người dùng bỏ trống/ngắt."""
    while True:
        try:
            line = input(
                "Repository cần quét (Enter để thoát): ").strip().strip('"')
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not line:
            return None
        path = Path(line).expanduser()
        if path.is_dir():
            return str(path.resolve())
        print(f"  không thấy thư mục: {path}", file=sys.stderr)


def choose() -> str:
    """Đọc một lựa chọn trong bảng chọn; 'q' khi stdin đóng hoặc bị ngắt.

    Coi mất nguồn nhập như người dùng rời đi: hỏi lại ở đây là vòng lặp vô hạn.
    """
    try:
        answer = input("Chọn [1]: ").strip().lower()
    except EOFError:
        return "q"
    except KeyboardInterrupt:
        print()
        return "q"
    return answer or "1"


def ask_effort() -> str:
    """Hỏi mức công; Enter là low. Đầu vào lạ thì nhắc lại một lần rồi về low."""
    try:
        answer = input(render_effort_prompt(
            color=banner.supports_color(sys.stdout))).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "low"
    shortcuts = {"l": "low", "m": "medium", "h": "high", "x": "max", "": "low"}
    effort = shortcuts.get(answer, answer)
    if effort not in EFFORTS:
        print(f"  không rõ mức công {answer!r} — dùng low", file=sys.stderr)
        return "low"
    return effort


def mode_of(answer: str) -> str | None:
    """Tên chế độ tương ứng lựa chọn; None khi thoát, chuỗi rỗng khi chọn sai."""
    answer = answer.strip().lower()
    if answer in ("q", "quit", "exit", "thoat", "thoát"):
        return None
    for key, name, _, _ in MODES:
        if answer in (key, name, name.rstrip("s")):
            return name
    return ""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    console.prefer_utf8(sys.stdout)
    console.prefer_utf8(sys.stderr)

    if argv and argv[0] in ("-h", "--help", "help"):
        return usage()
    # Lối in banner riêng — Security Lead dùng nó để mở màn trước khi hỏi.
    # Màu tự dò theo terminal (terminal thật có màu, ống dẫn của tool Bash thì
    # bản sạch không màu — TUI của Codev không render ANSI trong khung chat);
    # --color ép màu, --no-color hoặc NO_COLOR tắt hẳn.
    if argv and argv[0] == "banner":
        parser = argparse.ArgumentParser(
            prog="run.py banner", add_help=False, allow_abbrev=False)
        parser.add_argument("--palette", default=None, help="bảng màu banner")
        parser.add_argument(
            "--color", action="store_true",
            help="ép tô màu kể cả khi stdout không phải terminal")
        parser.add_argument("--no-color", action="store_true", help="cấm tô màu")
        flags, _ = parser.parse_known_args(argv[1:])
        banner.emit(
            palette=flags.palette or banner.DEFAULT_PALETTE,
            color=False if flags.no_color else True if flags.color else None,
        )
        return 0
    # Lối thẳng: `scan <repo> [cờ...]` — bảng chọn là lớp ngoài, không xen vào.
    if argv and argv[0] == "scan":
        return scan.main(argv[1:])

    parser = argparse.ArgumentParser(
        prog="run.py", add_help=False, allow_abbrev=False)
    parser.add_argument("repo", nargs="?", help="thư mục repository cần quét")
    parser.add_argument("--palette", default=None, help="bảng màu banner")
    known, extra = parser.parse_known_args(argv)

    repo = known.repo
    if repo:
        path = Path(repo).expanduser()
        if not path.is_dir():
            print(f"không thấy thư mục repository: {repo}", file=sys.stderr)
            return 1
        repo = str(path.resolve())

    quiet = "--quiet" in extra
    color = banner.supports_color(sys.stdout)
    if not quiet:
        banner.emit(palette=known.palette)

    if not repo:
        repo = ask_repo()
        if repo is None:
            return 0

    while not quiet:
        print(render_menu(repo, color=color))
        name = mode_of(choose())
        if name is None:
            return 0
        if not name:
            print("  chọn 1/2/3 hoặc q", file=sys.stderr)
            continue
        if name == "code-base":
            break
        # Hai chế độ còn lại: nói rõ là chưa có rồi quay lại bảng chọn.
        print(render_notice(name, NOT_READY[name], color=color))

    if "--effort" not in extra and not quiet:
        effort = ask_effort()
        extra = [*extra, "--effort", effort]

    if not quiet:
        print(
            banner.scan_subtitle("scan", _effort(extra), repo),
            file=sys.stderr,
        )
    return scan.main([repo, "--quiet", *extra])


def _effort(extra: list[str]) -> str:
    """Mức công trong cờ đã nhận; 'low' là mặc định của lượt quét."""
    if "--effort" in extra:
        position = extra.index("--effort")
        if position + 1 < len(extra):
            return extra[position + 1]
    return "low"


def run() -> int:
    try:
        return main()
    except KeyboardInterrupt:
        print("\nđã dừng", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(run())
