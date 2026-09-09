"""Đóng gói mã nguồn vào đề bài, cho runner gọi thẳng model.

Chạy qua Codev thì model tự đọc file bằng tool của nó. Gọi thẳng cổng thì
không có tool nào cả: model chỉ thấy đúng những gì ta đưa vào đề bài. Module
này chọn file, đánh số dòng, và cắt theo ngân sách ký tự.

Đánh số dòng là bắt buộc chứ không phải cho đẹp: model phải trả về số dòng của
finding, mà nó không đếm dòng đáng tin. Có số sẵn thì nó chép lại; dù vậy
`lib/source.py` vẫn định vị lại theo đoạn mã trích dẫn, vì model vẫn chép sai.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# Ngân sách mặc định cho phần mã nhét vào một đề bài (~30 nghìn token).
DEFAULT_BUDGET = 120_000
# Thư mục không mang mã của dự án.
SKIP_DIRS = frozenset(
    {
        ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
        "target", "build", "dist", "out", "bin", "obj", ".gradle", ".idea",
        ".mvn", "vendor", "third_party", ".next", ".nuxt", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", ".aiscan-run",
    }
)
# Đuôi file nhị phân hoặc sinh tự động: đọc vào chỉ tốn token.
SKIP_EXT = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
        ".pdf", ".zip", ".gz", ".tar", ".jar", ".war", ".class", ".exe",
        ".dll", ".so", ".dylib", ".pyc", ".pyo", ".woff", ".woff2", ".ttf",
        ".eot", ".mp4", ".mp3", ".wav", ".lock", ".min.js", ".map",
    }
)
# File dài hơn mức này gần như luôn là dữ liệu, không phải mã người viết.
MAX_FILE_CHARS = 60_000


def skipped_dir(name: str) -> bool:
    """Thư mục có bị bỏ qua khi duyệt cây không."""
    return name in SKIP_DIRS or name.startswith(".")


def skipped_file(path: Path) -> bool:
    """File có bị bỏ qua không, xét theo đuôi."""
    suffix = path.suffix.lower()
    return suffix in SKIP_EXT or path.name.startswith(".")


def listing(scan_root: str, paths: Sequence[str] | None = None, cap: int = 600) -> list[str]:
    """Đường dẫn tương đối của các file mã dưới `paths`, đã sắp xếp.

    `paths` là các thư mục của một component; None hoặc ["."] nghĩa là cả cây.
    """
    root = Path(scan_root)
    roots = [root] if not paths else [root / p for p in paths if p not in (".", "")]
    if not roots:
        roots = [root]

    found: list[str] = []
    for start in roots:
        if start.is_file():
            found.append(start.relative_to(root).as_posix())
            continue
        if not start.is_dir():
            continue
        for item in sorted(start.rglob("*")):
            if len(found) >= cap:
                break
            if not item.is_file() or skipped_file(item):
                continue
            if any(skipped_dir(part) for part in item.relative_to(root).parts[:-1]):
                continue
            found.append(item.relative_to(root).as_posix())
    return sorted(dict.fromkeys(found))[:cap]


def read_text(scan_root: str, file: str) -> str | None:
    """Nội dung `file`; None khi không đọc được hoặc trông như nhị phân."""
    try:
        raw = (Path(scan_root) / file).read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace")


def numbered(text: str, start: int = 1) -> str:
    """`text` với số dòng ở đầu mỗi dòng, canh phải."""
    lines = text.split("\n")
    width = len(str(start + len(lines) - 1))
    return "\n".join(f"{start + i:>{width}} | {line}" for i, line in enumerate(lines))


def window(scan_root: str, file: str, line: int, radius: int = 60) -> str:
    """Đoạn quanh `line` của `file`, đã đánh số; chuỗi rỗng khi không đọc được.

    Dùng cho hội đồng xác minh: giám khảo chỉ cần vùng quanh finding, nhét cả
    file vào là phí token mà không thêm thông tin.
    """
    text = read_text(scan_root, file)
    if text is None:
        return ""
    lines = text.split("\n")
    first = max(1, line - radius)
    last = min(len(lines), line + radius)
    return numbered("\n".join(lines[first - 1 : last]), start=first)


def pack(
    scan_root: str,
    files: Iterable[str],
    budget: int = DEFAULT_BUDGET,
) -> tuple[str, list[str], list[str]]:
    """Gói nội dung `files` thành một khối văn bản trong ngân sách ký tự.

    Trả về `(văn bản, file đã đưa vào, file bị bỏ vì hết chỗ)`. Danh sách bỏ
    sót được trả về chứ không nuốt: nó phải vào sổ độ phủ của báo cáo.
    """
    chunks: list[str] = []
    used = 0
    included: list[str] = []
    omitted: list[str] = []

    for file in files:
        if used >= budget:
            omitted.append(file)
            continue
        text = read_text(scan_root, file)
        if text is None:
            omitted.append(file)
            continue
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS]
        block = f"--- {file} ---\n{numbered(text)}\n"
        if used + len(block) > budget and included:
            omitted.append(file)
            continue
        chunks.append(block)
        used += len(block)
        included.append(file)

    return "\n".join(chunks), included, omitted
