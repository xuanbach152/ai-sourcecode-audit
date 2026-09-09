"""Gọi Codev Code ở chế độ không giao diện, và lấy khối JSON model trả về.

`codev run --format json` trả về luồng sự kiện chứ không phải structured
output theo schema, nên ở đây làm hai việc: gom phần văn bản model viết ra từ
luồng sự kiện đó, rồi trích khối JSON trong văn bản ấy. Model có thể viết thêm
lời dẫn quanh khối JSON — điều đó được chấp nhận, miễn là có đúng một khối đọc
được.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


from . import metrics


class CodevError(RuntimeError):
    """Codev không chạy được, hoặc trả về thứ không đọc được thành JSON."""

    def __init__(self, message: str, reply: "Reply | None" = None) -> None:
        super().__init__(message)
        # Mot luot hong VAN da tieu token. Kem so do vao loi de so sach khong
        # bi hut mat phan chi phi that su da bo ra.
        self.reply = reply


def collect_text(payload: object, out: list[str]) -> None:
    """Gom mọi trường văn bản trong luồng sự kiện JSON của Codev vào `out`.

    Hình dạng sự kiện có thể đổi giữa các phiên bản, nên đi đệ quy theo các
    khoá văn bản đã biết thay vì bám vào một schema cứng.
    """
    if isinstance(payload, str):
        out.append(payload)
    elif isinstance(payload, list):
        for item in payload:
            collect_text(item, out)
    elif isinstance(payload, dict):
        for key in ("part", "text", "content", "message", "parts", "output", "result"):
            if key in payload:
                collect_text(payload[key], out)


def events(stdout: str) -> list[object]:
    """Các sự kiện Codev in ra: một JSON mỗi dòng, hoặc một JSON cho cả luồng."""
    stripped = stdout.strip()
    if not stripped:
        return []
    try:
        return [json.loads(stripped)]
    except ValueError:
        pass
    parsed: list[object] = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed.append(json.loads(line))
        except ValueError:
            continue
    return parsed


def spoken(stdout: str) -> str:
    """Phần văn bản model nói ra, tách khỏi vỏ sự kiện của `--format json`.

    Trả lại nguyên `stdout` khi không bóc được gì — Codev đổi định dạng thì
    vẫn còn đường đọc được, thay vì hỏng hẳn.
    """
    chunks: list[str] = []
    for event in events(stdout):
        collect_text(event, chunks)
    return "\n".join(chunks) if chunks else stdout.strip()


def fenced_blocks(text: str) -> list[str]:
    """Nội dung mọi khối ``` trong `text`, khối ngoài cùng trước."""
    blocks = []
    marker = "```"
    position = text.find(marker)
    while position != -1:
        opened = text.find("\n", position)
        if opened == -1:
            break
        closed = text.find(marker, opened)
        if closed == -1:
            break
        blocks.append(text[opened + 1 : closed])
        position = text.find(marker, closed + len(marker))
    return blocks


def balanced(text: str) -> str | None:
    """Đối tượng JSON cân ngoặc đầu tiên trong `text`, bỏ qua ngoặc trong chuỗi."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for position in range(start, len(text)):
        char = text[position]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : position + 1]
    return None


def extract_json(text: str) -> object:
    """Đối tượng JSON model trả về; CodevError khi không có cái nào đọc được."""
    for candidate in [*fenced_blocks(text), text]:
        block = balanced(candidate)
        if block is None:
            continue
        try:
            return json.loads(block)
        except ValueError:
            continue
    head = text.strip()[:160]
    msg = f"câu trả lời không chứa khối JSON đọc được; 160 ký tự đầu: {head!r}"
    raise CodevError(msg)


@dataclass(frozen=True)
class Reply:
    """Cau tra loi cua mot luot goi, kem so lieu do duoc."""

    data: object
    stdout: str
    seconds: float
    tokens_in: int
    tokens_out: int
    estimated: bool


@dataclass(frozen=True)
class Runner:
    """Một cách gọi Codev. `command` tách ra để test thay được bằng script giả."""

    command: Sequence[str] = field(default_factory=lambda: ("codev",))
    model: str | None = None
    timeout: int = 900
    cwd: str | None = None
    # Duong dan codev.json khai bao cac agent aiscan-*. Lenh chay trong repo
    # duoc quet, ma repo do khong co dinh nghia agent, nen phai tro CODEV_CONFIG.
    config: str | None = None
    # Codev cho model bo tool doc file, nen pipeline khong phai nhet ma nguon
    # vao de bai. Runner goi thang cong dat co nay False.
    provides_tools: bool = True

    def environ(self) -> dict[str, str] | None:
        """Bien moi truong cho lenh con, hoac None de ke thua nguyen ban."""
        if not self.config:
            return None
        return {**os.environ, "CODEV_CONFIG": self.config}

    def program(self) -> str:
        """Đường dẫn đầy đủ của lệnh chạy.

        Trên Windows `codev` là `codev.CMD`; subprocess không tự thêm đuôi từ
        PATHEXT nên phải tự giải, nếu không sẽ hỏng với WinError 2.
        """
        first = self.command[0]
        return shutil.which(first) or first

    def argv(self, agent: str) -> list[str]:
        """Dòng lệnh gọi một agent; đề bài đi qua stdin chứ không qua argv.

        Trên Windows argv bị chặn ở ~32k ký tự (WinError 206), mà đề bài có thể
        mang cả cây mã nguồn — nên tin nhắn không bao giờ nằm trên dòng lệnh.
        """
        argv = [self.program(), *self.command[1:], "run", "--agent", agent, "--format", "json"]
        if self.model:
            argv += ["--model", self.model]
        return argv

    def ask(self, agent: str, message: str) -> Reply:
        """Gọi `agent` với `message`; CodevError khi không chạy được hoặc không đọc được."""
        argv = self.argv(agent)
        started = time.monotonic()
        try:
            done = subprocess.run(  # noqa: S603 - argv dựng từ hằng số, không qua shell
                argv,
                input=message,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
                env=self.environ(),
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as error:
            msg = f"không chạy được {argv[0]!r}: {error}"
            raise CodevError(msg) from error
        except subprocess.TimeoutExpired as error:
            msg = f"agent {agent!r} quá {self.timeout}s không trả lời"
            raise CodevError(msg) from error
        seconds = time.monotonic() - started
        if done.returncode != 0:
            tail = (done.stderr or done.stdout).strip()[-400:]
            msg = f"agent {agent!r} thoát mã {done.returncode}: {tail}"
            raise CodevError(msg)

        stream = events(done.stdout)
        text = spoken(done.stdout)
        # Codev báo token trong sự kiện step_finish, ở part.tokens.
        reported = metrics.usage_of(stream)
        if reported is None:
            tokens_in, tokens_out, estimated = (
                metrics.estimate(message),
                metrics.estimate(text),
                True,
            )
        else:
            tokens_in, tokens_out, estimated = reported[0], reported[1], False
        measured = Reply(
            data=None,
            stdout=done.stdout,
            seconds=seconds,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated=estimated,
        )
        try:
            data = extract_json(text)
        except CodevError as error:
            raise CodevError(str(error), measured) from None
        return replace(measured, data=data)
