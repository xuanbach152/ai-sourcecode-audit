#!/usr/bin/env python3
"""Điểm khởi động AIScan — chạy được ngay, không cần cấu hình gì.

    python run.py                     banner + hỏi repo + bảng chọn
    python run.py <repo>              banner + bảng chọn cho repo đó
    python run.py scan <repo>         quét thẳng code-base, không hỏi

Tên file phải khác `aiscan`: đặt `aiscan.py` cạnh package `aiscan/` làm
`python -m aiscan` tìm thấy file này trước package và hỏng im lặng.

File này tự lo hai thứ mà trước đây bắt người dùng nhớ: đưa thư mục chứa
package `aiscan/` vào đường dẫn import, và nạp `.env` để có khoá cổng. Nhờ vậy
không cần PYTHONPATH, không cần `set -a && . ../.env`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_env() -> Path | None:
    """Nạp `.env` tìm được ở thư mục này hoặc các thư mục cha; trả về file đã nạp.

    Biến đã có sẵn trong môi trường thì giữ nguyên — dòng lệnh luôn thắng file.
    """
    for folder in (HERE, *HERE.parents):
        candidate = folder / ".env"
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name, value = name.strip(), value.strip().strip("'\"")
            if name and name not in os.environ:
                os.environ[name] = value
        return candidate
    return None


def main() -> int:
    sys.path.insert(0, str(HERE))
    load_env()

    from aiscan.cli import entry

    return entry.main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
