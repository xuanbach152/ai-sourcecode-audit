"""Chạy một lượt quét: `python -m aiscan.orchestrator <run_dir> <scan_root> ...`

Ghi file kết quả vào thư mục chạy rồi in đường dẫn của nó. Bước tiếp theo là
đưa file đó cho `save_result.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from aiscan.lib import banner, console, identity, strictjson

from . import corpus, plan
from .codev import Runner
from .direct import DirectRunner
from .scan import Budget, Context, Scan


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="aiscan.orchestrator", allow_abbrev=False)
    parser.add_argument("run_dir", help=f"thư mục {identity.RUN_DIR_NAME} của lượt quét")
    parser.add_argument("scan_root", help="thư mục gốc của repo cần quét")
    parser.add_argument("--effort", required=True, choices=("low", "medium", "high", "max"))
    parser.add_argument("--mode", default="scan", choices=identity.MODES)
    parser.add_argument("--scope", default="", help="danh sách thư mục, ngăn bằng dấu phẩy")
    parser.add_argument("--change", default="", help="mô tả thay đổi khi quét diff")
    parser.add_argument(
        "--runner",
        default="direct",
        choices=("direct", "codev"),
        help="direct = gọi thẳng cổng LLM (mặc định); codev = chạy qua Codev Code",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="direct: MiniMax/MiniMax-M3 · codev: aigw/MiniMax/MiniMax-M3",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="URL cổng cho runner direct; mặc định lấy từ AIGW_BASE_URL",
    )
    parser.add_argument(
        "--api-key-env",
        default="AIGW_API_KEY",
        help="tên biến môi trường chứa khoá cổng",
    )
    parser.add_argument(
        "--code-budget",
        type=int,
        default=None,
        help="số ký tự mã nguồn nhét vào mỗi đề bài (runner direct)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=12000,
        help="giới hạn token model sinh ra mỗi lượt. M3 là model suy luận nên cần rộng",
    )
    parser.add_argument("--codev", default="codev", help="lệnh gọi Codev (đổi được để test)")
    parser.add_argument(
        "--codev-config",
        # __main__.py -> orchestrator -> aiscan -> phat_trien_loi -> goc repo
        default=str(Path(__file__).resolve().parents[3] / "codev.json"),
        help="codev.json khai báo các agent aiscan-* (đặt vào CODEV_CONFIG)",
    )
    parser.add_argument("--budget", type=int, default=120, help="trần số lượt gọi agent")
    parser.add_argument("--workers", type=int, default=4, help="số lượt gọi chạy song song")
    parser.add_argument("--timeout", type=int, default=900, help="giây cho mỗi lượt gọi")
    parser.add_argument("--shard", type=int, default=1, help="số thứ tự lượt chạy")
    parser.add_argument("--next-id", type=int, default=1, help="số hiệu finding còn trống")
    parser.add_argument("--large", action="store_true", help="repo lớn: bám attack surface")
    parser.add_argument("--quiet", action="store_true", help="không in banner")
    parser.add_argument(
        "--no-log-calls",
        action="store_true",
        help="không ghi log từng lượt gọi (mặc định có ghi, vào <run_dir>/calls/)",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=14_000_000,
        help="hạn mức token để đối chiếu trong bảng tổng hợp",
    )
    return parser.parse_args(argv)


def resolved_config(source: Path, run_dir: Path) -> Path:
    """Bản sao của `source` với nội dung prompt nhúng thẳng vào.

    `codev.json` trong repo dùng `{file:./prompts/...}` cho người đọc dễ theo
    dõi, nhưng Codev giải tham chiếu đó theo thư mục đang chạy — mà orchestrator
    chạy trong repo bị quét, không phải repo công cụ — và còn cắt cụt đường dẫn
    tuyệt đối. Nên bản dùng thật nhúng nguyên văn prompt, không còn tham chiếu
    file nào để giải sai.
    """
    marker = "{file:"
    base = source.parent.resolve()
    config = json.loads(source.read_text(encoding="utf-8"))
    agents = config.get("agent")
    if isinstance(agents, dict):
        for name, spec in agents.items():
            if not isinstance(spec, dict):
                continue
            prompt = spec.get("prompt")
            if not isinstance(prompt, str) or not prompt.startswith(marker):
                continue
            ref = prompt[len(marker) : -1] if prompt.endswith("}") else prompt[len(marker) :]
            path = Path(ref) if Path(ref).is_absolute() else base / ref
            try:
                spec["prompt"] = path.read_text(encoding="utf-8")
            except OSError as error:
                msg = f"agent {name!r}: khong doc duoc prompt {path}: {error}"
                raise SystemExit(msg) from error

    target = run_dir / "codev.resolved.json"
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main(argv: list[str]) -> int:
    # Ep UTF-8 TRUOC khi parse: argparse in phan tro giup tieng Viet ngay trong
    # parse_args, console cp1252 se vo neu chua doi bang ma.
    console.prefer_utf8(sys.stdout)
    console.prefer_utf8(sys.stderr)
    args = parse(argv)

    run_dir = Path(args.run_dir)
    if run_dir.name != identity.RUN_DIR_NAME:
        sys.stderr.write(f"{run_dir} không phải thư mục {identity.RUN_DIR_NAME}\n")
        return 1
    if not run_dir.is_dir():
        sys.stderr.write(f"{run_dir} chưa tồn tại; chạy write_scan_meta.py trước\n")
        return 1

    scope = tuple(s.strip() for s in args.scope.split(",") if s.strip())
    # write_scan_meta.py da ghi so file vao scan-meta.json truoc buoc nay.
    effort = plan.effort_of(args.effort, counted=(run_dir / 'scan-meta.json').is_file())
    if not args.quiet:
        banner.emit(sys.stderr, subtitle=banner.scan_subtitle(args.mode, args.effort, args.scan_root))

    context = Context(
        scan_root=str(Path(args.scan_root).resolve()),
        effort=effort,
        mode=args.mode,
        change=args.change,
        scope=scope,
        large=args.large,
        workers=args.workers,
        code_budget=args.code_budget or corpus.DEFAULT_BUDGET,
        log=lambda line: print(line, file=sys.stderr, flush=True),
    )
    if args.runner == "direct":
        base = args.base_url or os.environ.get("AIGW_BASE_URL", "")
        key = os.environ.get(args.api_key_env, "")
        if not base or not key:
            sys.stderr.write(
                f"runner direct can --base-url (hoac AIGW_BASE_URL) va bien "
                f"{args.api_key_env}; nap bang: set -a && . ../.env && set +a\n"
            )
            return 1
        runner = DirectRunner(
            base_url=base,
            api_key=key,
            model=args.model or "MiniMax/MiniMax-M3",
            prompts_dir=Path(__file__).resolve().parents[2] / "prompts",
            timeout=args.timeout,
            max_tokens=args.max_tokens,
        )
    else:
        config = Path(args.codev_config)
        if not config.is_file():
            sys.stderr.write(
                f"khong thay {config}: Codev se khong tim duoc cac agent aiscan-*\n"
            )
            return 1
        runner = Runner(
            command=tuple(shlex.split(args.codev)),
            model=args.model,
            timeout=args.timeout,
            cwd=context.scan_root,
            config=str(resolved_config(config, run_dir)),
        )
    log_dir = None if args.no_log_calls else run_dir / "calls"
    scan = Scan(runner, context, Budget(args.budget), log_dir=log_dir)
    # abspath chu khong phai resolve: save_result.py so sanh bang abspath.
    try:
        result = scan.run(os.path.abspath(args.run_dir), next_id=args.next_id, shard=args.shard)
    except KeyboardInterrupt:
        # Ghi lại số đo tới thời điểm hủy: đã tiêu token thì phải hiện trong sổ.
        measured = scan.metrics.to_dict(budget=args.token_budget)
        (run_dir / "metrics.json").write_text(
            strictjson.text(measured, indent=2) + chr(10), encoding="utf-8"
        )
        sys.stderr.write(
            f"\n! đã hủy lượt quét theo Ctrl+C — các lượt đang bay sẽ tự kết thúc "
            f"theo timeout. Số đo tạm thời: {run_dir / 'metrics.json'}\n"
        )
        return 130

    out = run_dir / f"orchestrator-result-{args.shard}.json"
    out.write_text(strictjson.text(result, indent=2) + "\n", encoding="utf-8")

    measured = scan.metrics.to_dict(budget=args.token_budget)
    (run_dir / "metrics.json").write_text(
        strictjson.text(measured, indent=2) + chr(10), encoding="utf-8"
    )

    kept = len(result["result"]["findings"])
    pending = len(result["result"]["pending"])
    print("", file=sys.stderr)
    print(scan.metrics.table(budget=args.token_budget), file=sys.stderr)
    print("", file=sys.stderr)
    print(f"findings: {kept}", file=sys.stderr)
    print(f"pending: {pending}", file=sys.stderr)
    print(f"agent_calls: {scan.budget.used}/{scan.budget.limit}", file=sys.stderr)
    if log_dir is not None:
        print(f"log tung luot: {log_dir}", file=sys.stderr)
    print(str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
