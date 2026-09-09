"""Chấm một báo cáo AIScan so với đáp án của fixture.

    python fixtures/score.py <thu_muc_bao_cao> [--expected fixtures/vuln-webapp/expected.json]

Khớp một finding với một mục đáp án khi trùng file và trùng CWE. Không đòi
trùng số dòng: model hay lệch vài dòng, mà lệch dòng thì lập trình viên vẫn tìm
ra lỗi — đòi trùng tuyệt đối sẽ làm recall trông tệ hơn thực tế. Số dòng vẫn
được in ra để soi.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_findings(report: Path) -> list[dict]:
    """Các finding trong AISCAN-RESULTS.jsonl."""
    path = report / "AISCAN-RESULTS.jsonl"
    if not path.is_file():
        raise SystemExit(f"khong thay {path}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def normal(cwe: str) -> str:
    """`CWE-89` từ mọi cách viết thường gặp."""
    text = str(cwe or "").strip().upper().replace("_", "-")
    if text.startswith("CWE-"):
        text = text[4:]
    return f"CWE-{text.strip()}" if text.strip().isdigit() else "CWE-?"


def tail(path: str) -> str:
    """Đuôi đường dẫn, để so khớp bất kể tiền tố thư mục."""
    return str(path or "").replace("\\", "/").lstrip("./")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="score.py", allow_abbrev=False)
    parser.add_argument("report", help="thư mục báo cáo AISCAN-*")
    parser.add_argument(
        "--expected",
        default=str(Path(__file__).parent / "vuln-webapp" / "expected.json"),
        help="file đáp án",
    )
    args = parser.parse_args(argv)

    answer = json.loads(Path(args.expected).read_text(encoding="utf-8"))
    wanted = answer["vulnerabilities"]
    clean = {tail(f) for f in answer.get("clean_files", [])}
    found = load_findings(Path(args.report))

    matched: dict[str, dict] = {}
    extra: list[dict] = []
    for item in found:
        file, cwe = tail(item.get("file")), normal(item.get("cwe_id"))
        hit = next(
            (
                v
                for v in wanted
                if v["id"] not in matched and tail(v["file"]) == file and normal(v["cwe"]) == cwe
            ),
            None,
        )
        if hit:
            matched[hit["id"]] = item
        else:
            extra.append(item)

    missed = [v for v in wanted if v["id"] not in matched]
    true_positive, false_positive, false_negative = len(matched), len(extra), len(missed)
    precision = true_positive / (true_positive + false_positive) if found else 0.0
    recall = true_positive / len(wanted) if wanted else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    print(f"Bao cao: {args.report}")
    print(f"Dap an : {len(wanted)} lo hong co chu dich\n")

    print(f"TIM DUNG ({true_positive})")
    for key, item in sorted(matched.items()):
        spec = next(v for v in wanted if v["id"] == key)
        drift = int(item.get("line") or 0) - spec["line"]
        note = "" if drift == 0 else f"  (lech {drift:+d} dong)"
        print(f"  {key:<4} {spec['cwe']:<9} {tail(spec['file'])}:{spec['line']}{note}")

    print(f"\nBO SOT ({false_negative})")
    for spec in missed:
        print(f"  {spec['id']:<4} {spec['cwe']:<9} {tail(spec['file'])}:{spec['line']}  {spec['title']}")

    print(f"\nBAO THEM ({false_positive})")
    for item in extra:
        file = tail(item.get("file"))
        flag = "  <-- FILE SACH, chac chan la bao nham" if file in clean else ""
        print(f"  {normal(item.get('cwe_id')):<9} {file}:{item.get('line')}  {item.get('title')}{flag}")

    print("\n" + "-" * 52)
    print(f"Precision {precision:6.1%}   (dung / tong so bao)")
    print(f"Recall    {recall:6.1%}   (dung / tong so lo hong that)")
    print(f"F1        {f1:6.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
