"""Tên cố định của AIScan: tên công cụ, thư mục chạy, tiền tố thư mục báo cáo.

Mọi chỗ trong mã nguồn gọi tên công cụ đều lấy từ đây. Đổi tên công cụ thì
chỉ sửa file này.
"""

from __future__ import annotations

import re

NAME = "aiscan"
VERSION = "0.1.0"
# Thư mục làm việc tạm của một lượt quét, nằm trong thư mục báo cáo.
RUN_DIR_NAME = ".aiscan-run"
TARGET_FILES_NAME = "target-files.json"
# Bộ điều phối (orchestrator) phải ghi đúng chuỗi này vào mỗi bản ghi phiếu bầu
# nó tính ra; save_result.py và render_report.py từ chối bản ghi không có nó.
VOTES_PROVENANCE = "aiscan/panel"
MODES = ("scan", "changes", "commit")
REPORT_DIR_PREFIX = "AISCAN-"
# \Z chứ không phải $: `$` khớp cả trước ký tự xuống dòng cuối, mà id này đặt tên file sản phẩm.
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}\Z")


def version() -> str | None:
    """Phiên bản công cụ ghi vào SARIF; None nếu chưa đặt."""
    return VERSION.strip() or None
