"""Một lệnh chạy trọn lượt quét: `python -m aiscan scan <repo>`.

Gộp bốn bước lại — ghi bối cảnh, chạy pipeline, gộp kết quả, xuất sản phẩm —
và tự dựng thư mục báo cáo. Bốn lệnh con vẫn dùng riêng được khi cần soi từng
bước; lệnh này chỉ là lối đi thẳng cho trường hợp thường gặp.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiscan.lib import banner, console, identity, strictjson

from . import render_report, report_md, save_result, write_scan_meta


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aiscan scan",
        description="Quét một repository và xuất báo cáo, trong một lệnh.",
        allow_abbrev=False,
    )
    parser.add_argument("repo", help="thư mục repository cần quét")
    parser.add_argument(
        "--mode",
        default="scan",
        choices=identity.MODES,
        help="code-base (mặc định) · changes · commit — hai chế độ sau chưa có điều phối diff",
    )
    parser.add_argument(
        "--effort",
        default="low",
        choices=("low", "medium", "high", "max"),
        help="mức công (mặc định low: rẻ nhất, một lượt nghiên cứu)",
    )
    parser.add_argument("--out", default=None, help="thư mục báo cáo (mặc định nằm trong repo)")
    parser.add_argument("--runner", default="direct", choices=("direct", "codev"))
    parser.add_argument("--model", default=None, help="mặc định MiniMax/MiniMax-M3")
    parser.add_argument(
        "--budget",
        type=int,
        default=80,
        help="trần số lượt gọi agent. Mỗi ứng viên tốn 3 lượt cho hội đồng",
    )
    parser.add_argument("--workers", type=int, default=6, help="số lượt gọi song song")
    parser.add_argument("--timeout", type=int, default=600, help="giây cho mỗi lượt gọi")
    parser.add_argument("--max-tokens", type=int, default=12000)
    parser.add_argument("--scope", default="", help="chỉ quét các thư mục này, ngăn bằng dấu phẩy")
    parser.add_argument("--large", action="store_true", help="repo lớn: bám attack surface")
    parser.add_argument("--keep-run-dir", action="store_true", help="giữ lại thư mục chạy tạm")
    parser.add_argument("--quiet", action="store_true", help="không in banner")
    return parser.parse_args(argv)


def load_pending(run_dir: Path) -> int:
    """Số ứng viên lượt này để lại cho lượt sau; 0 khi không đọc được."""
    try:
        votes = strictjson.load(run_dir / "votes.json")
    except (OSError, ValueError):
        return 0
    if not isinstance(votes, dict):
        return 0
    count = votes.get("unreviewed_candidate_sites")
    return count if isinstance(count, int) and count > 0 else 0


def step(number: int, total: int, text: str) -> None:
    """Một dòng tiến độ, ra stderr để stdout chỉ mang đường dẫn báo cáo."""
    print(f"\n[{number}/{total}] {text}", file=sys.stderr, flush=True)


def main(argv: list[str]) -> int:
    console.prefer_utf8(sys.stdout)
    console.prefer_utf8(sys.stderr)
    args = parse(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write(f"khong thay repository: {repo}\n")
        return 1

    if args.mode != "scan":
        sys.stderr.write(
            f"che do {args.mode!r} chua co dieu phoi diff trong ban nay — pipeline chưa tính "
            "merge-base/numstat nên chưa quét đúng 'thay đổi'. Chạy --mode scan, hoặc đợi bản sau.\n"
        )
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    report = Path(args.out).resolve() if args.out else repo / f"{identity.REPORT_DIR_PREFIX}{stamp}"
    run_dir = report / identity.RUN_DIR_NAME
    run_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        banner.emit(sys.stderr, subtitle=banner.scan_subtitle(args.mode, args.effort, str(repo)))

    total = 5
    step(1, total, "Ghi bối cảnh lượt quét")
    try:
        meta_argv = [str(run_dir), str(repo), "--mode", args.mode, "--effort", args.effort]
        if args.scope:
            meta_argv += ["--scope", args.scope]
        if write_scan_meta.main(meta_argv) != 0:
            return 1

        step(2, total, "Chạy pipeline — Ctrl+C hủy bất cứ lúc nào (đây là chỗ gọi AI)")
        # Nap muon: orchestrator keo theo phan mang, khong can khi chi doc bao cao.
        from aiscan.orchestrator.__main__ import main as orchestrate

        scan_argv = [
            str(run_dir), str(repo),
            "--effort", args.effort,
            "--mode", args.mode,
            "--runner", args.runner,
            "--budget", str(args.budget),
            "--workers", str(args.workers),
            "--timeout", str(args.timeout),
            "--max-tokens", str(args.max_tokens),
            "--quiet",
        ]
        if args.model:
            scan_argv += ["--model", args.model]
        if args.scope:
            scan_argv += ["--scope", args.scope]
        if args.large:
            scan_argv.append("--large")
        if orchestrate(scan_argv) != 0:
            return 1

        step(3, total, "Gộp kết quả và kiểm phiếu")
        result = run_dir / "orchestrator-result-1.json"
        if save_result.main([str(result), str(run_dir)]) != 0:
            sys.stderr.write("save_result tu choi ket qua; xem thong bao ben tren\n")
            return 1

        step(4, total, "Dựng báo cáo")
        (run_dir / f"{identity.REPORT_DIR_PREFIX}RESULTS.md").write_text(
            report_md.build(run_dir), encoding="utf-8"
        )

        # Ngan sach het giua chung la ly do pho bien nhat khien recall thap: ung
        # vien tim ra roi nhung khong du luot goi de hoi dong bo phieu.
        pending = load_pending(run_dir)
        if pending:
            print(
                f"\n! {pending} ứng viên chưa được hội đồng xét vì hết ngân sách.\n"
                f"  Chạy lại với --budget {args.budget + pending * 3} để xét hết.",
                file=sys.stderr,
            )

        step(5, total, "Xuất SARIF và JSONL")
        render_argv = [str(run_dir), "--products-dir", str(report)]
        if render_report.main(render_argv) != 0:
            return 1
    except KeyboardInterrupt:
        sys.stderr.write(
            f"\n! đã hủy lượt quét. Đã tiêu token vẫn được ghi ở "
            f"{run_dir / 'calls'} — không có báo cáo, xóa {report} nếu không cần.\n"
        )
        return 130

    print(f"\nBáo cáo: {report}", file=sys.stderr)
    for name in sorted(p.name for p in report.iterdir() if p.is_file()):
        print(f"  {name}", file=sys.stderr)
    print(str(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
