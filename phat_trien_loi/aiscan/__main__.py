"""`python -m aiscan` — điểm vào của công cụ khi đã có package trên sys.path.

Cách chạy không cần cấu hình là `python run.py` (thư mục gốc `phat_trien_loi/`).

    python -m aiscan scan <repo>      quét một repository, trọn một lệnh
    python -m aiscan                  in banner và danh sách lệnh
"""

from __future__ import annotations

import sys

from aiscan.lib import banner, console

COMMANDS = (
    ("scan <repo>", "quét một repository và xuất báo cáo, trọn một lệnh"),
)

DETAILS = (
    ("aiscan.cli.write_scan_meta", "ghi bối cảnh: revision, remote, danh sách file"),
    ("aiscan.orchestrator", "chạy pipeline 7 giai đoạn — chỗ duy nhất gọi AI"),
    ("aiscan.cli.save_result", "gộp kết quả một lượt, kiểm phiếu"),
    ("aiscan.cli.render_report", "xuất AISCAN-RESULTS.jsonl / .sarif"),
    ("aiscan.cli.patch_artifacts", "sinh file .patch từ finding"),
)


def usage() -> int:
    """Banner, lệnh chính, và các lệnh con dùng khi cần soi từng bước."""
    console.prefer_utf8(sys.stdout)
    banner.emit()
    print()
    print("Lệnh:")
    for name, purpose in COMMANDS:
        print(f"  python -m aiscan {name:<16} {purpose}")
    print()
    print("Chạy thử ngay (run.py tự nạp .env, không cần cài gì):")
    print("  python run.py fixtures/vuln-webapp       banner + bảng chọn chế độ")
    print("  python run.py scan fixtures/vuln-webapp  quét thẳng code-base")
    print()
    print("Từng bước riêng, khi cần soi:")
    for name, purpose in DETAILS:
        print(f"  python -m {name:<28} {purpose}")
    print()
    print("Bảng màu banner: " + ", ".join(banner.PALETTES) + "  (--palette <tên>)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "scan":
        from aiscan.cli import scan

        return scan.main(argv[1:])
    if argv and argv[0] == "--palette" and len(argv) > 1:
        console.prefer_utf8(sys.stdout)
        banner.emit(palette=argv[1])
        return 0
    if argv and argv[0] not in ("-h", "--help", "help"):
        sys.stderr.write(f"khong biet lenh {argv[0]!r}\n")
        usage()
        return 2
    return usage()


if __name__ == "__main__":
    sys.exit(main())
