"""Banner của AIScan: chữ ký hình ảnh in ra khi công cụ khởi động.

In ra stdout khi chạy `python -m aiscan`, ra stderr khi một lệnh CLI muốn
chào mà không được làm bẩn stdout (stdout của các lệnh là dữ liệu máy đọc).
Tự tắt màu khi đầu ra không phải terminal hoặc khi có NO_COLOR, và tự hạ
xuống bản ASCII thuần khi console không mã hoá nổi ký tự khối.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from . import console, identity

if TYPE_CHECKING:
    from typing import IO

ART = (
    " █████╗ ██╗███████╗ ██████╗ █████╗ ███╗   ██╗",
    "██╔══██╗██║██╔════╝██╔════╝██╔══██╗████╗  ██║",
    "███████║██║███████╗██║     ███████║██╔██╗ ██║",
    "██╔══██║██║╚════██║██║     ██╔══██║██║╚██╗██║",
    "██║  ██║██║███████║╚██████╗██║  ██║██║ ╚████║",
    "╚═╝  ╚═╝╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝",
)

ART_ASCII = (
    "    _    ___ ____   ____    _    _   _ ",
    "   / \\  |_ _/ ___| / ___|  / \\  | \\ | |",
    "  / _ \\  | |\\___ \\| |     / _ \\ |  \\| |",
    " / ___ \\ | | ___) | |___ / ___ \\| |\\  |",
    "/_/   \\_\\___|____/ \\____/_/   \\_\\_| \\_|",
)

# Một nấc màu cho mỗi dòng chữ. Đổi bảng màu bằng --palette.
PALETTES = {
    # Ngọc lam chuyển sang chàm: mát, đọc rõ trên cả nền sáng lẫn nền tối.
    "ocean": (
        (34, 211, 238),
        (34, 190, 245),
        (56, 160, 248),
        (79, 130, 246),
        (109, 108, 240),
        (139, 92, 230),
    ),
    # Bảng cũ: đỏ chuyển sang hổ phách.
    "ember": (
        (214, 48, 49),
        (225, 76, 52),
        (235, 106, 56),
        (243, 137, 62),
        (249, 168, 70),
        (252, 196, 82),
    ),
    # Xanh lá chuyển sang ngọc lam: dịu, hợp log CI chạy dài.
    "mint": (
        (52, 211, 153),
        (45, 212, 191),
        (34, 211, 238),
        (56, 189, 248),
        (96, 165, 250),
        (129, 140, 248),
    ),
}
DEFAULT_PALETTE = "ocean"

TAGLINE = "AI review source code"
TAGLINE_ASCII = TAGLINE
RULE = "─"
RULE_ASCII = "-"

RESET = "\x1b[0m"
DIM = "\x1b[2m"
BOLD = "\x1b[1m"
ACCENT = "\x1b[38;2;125;211;252m"
GREY = "\x1b[38;2;122;134;150m"


def supports_color(stream: IO[str]) -> bool:
    """Có nên tô màu cho `stream` hay không."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def _paint(text: str, code: str, *, color: bool) -> str:
    """`text` trong màu `code`, hoặc nguyên văn khi không tô màu."""
    return f"{code}{text}{RESET}" if color else text


def render(
    *,
    color: bool = False,
    unicode: bool = True,
    subtitle: str = "",
    palette: str = DEFAULT_PALETTE,
) -> str:
    """Banner đầy đủ dưới dạng một chuỗi, không có ký tự xuống dòng ở cuối.

    `subtitle` là dòng ngữ cảnh tuỳ chọn của lượt chạy (chế độ, mức công, thư mục).
    """
    art = ART if unicode else ART_ASCII
    rule_char = RULE if unicode else RULE_ASCII
    ramp = PALETTES.get(palette, PALETTES[DEFAULT_PALETTE])
    width = max(len(line) for line in art)

    lines = []
    for position, line in enumerate(art):
        if color:
            red, green, blue = ramp[position % len(ramp)]
            line = f"\x1b[38;2;{red};{green};{blue}m{line}{RESET}"
        lines.append(line)

    lines.append("")
    lines.append(_paint(rule_char * width, GREY, color=color))
    lines.append(_paint(TAGLINE if unicode else TAGLINE_ASCII, BOLD, color=color))
    dot = "  ·  " if unicode else "  |  "
    stamp = dot.join((f"v{identity.VERSION}", "Codev / Viettel VTNET"))
    lines.append(_paint(stamp, ACCENT, color=color))
    if subtitle:
        lines.append(_paint(subtitle, DIM, color=color))
    lines.append(_paint(rule_char * width, GREY, color=color))
    return "\n".join(lines)


def emit(
    stream: IO[str] | None = None,
    *,
    subtitle: str = "",
    palette: str = DEFAULT_PALETTE,
    color: bool | None = None,
) -> None:
    """In banner ra `stream` (mặc định stdout), không bao giờ ném lỗi.

    `color` None nghĩa là tự dò (terminal thật mới tô màu); True/False ép theo.
    Console Windows dùng bảng mã cũ không in nổi ký tự khối; khi đó hạ xuống
    bản ASCII thay vì làm hỏng lệnh đang chạy.
    """
    out = sys.stdout if stream is None else stream
    console.prefer_utf8(out)
    if color is None:
        color = supports_color(out)
    for unicode in (True, False):
        try:
            out.write(
                render(color=color, unicode=unicode, subtitle=subtitle, palette=palette) + "\n"
            )
        except UnicodeEncodeError:
            continue
        except OSError:
            return
        else:
            return


def scan_subtitle(mode: str, effort: str, scan_root: str) -> str:
    """Dòng ngữ cảnh của một lượt quét, đặt dưới banner."""
    return f"che do {mode}  |  muc co gang {effort}  |  {scan_root}"
