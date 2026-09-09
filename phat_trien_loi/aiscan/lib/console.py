"""The scripts' console output: undecodable path names and failed removals, printed readably."""

from __future__ import annotations

import io
import sys


def tolerate_undecodable_names() -> None:
    """Make stdout print an undecodable path name as escapes instead of raising."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")


def prefer_utf8(stream: object) -> None:
    """Chuyển `stream` sang UTF-8 nếu được, để chữ tiếng Việt không làm vỡ lệnh.

    Console Windows mặc định dùng bảng mã cũ (cp1252, cp437); ghi chữ có dấu
    vào đó ném UnicodeEncodeError giữa chừng. Ký tự nào bảng mã đích vẫn không
    nhận thì in ra dạng escape thay vì ném lỗi.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="backslashreplace")
    except (OSError, ValueError, LookupError):
        try:
            reconfigure(errors="backslashreplace")
        except (OSError, ValueError, LookupError):
            return


def removal_failure_detail(error: OSError) -> object:
    """The operator-readable reason a tree removal failed."""
    return str(error) if error.strerror or not error.args else error.args[0]
