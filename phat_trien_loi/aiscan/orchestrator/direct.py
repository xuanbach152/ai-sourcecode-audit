"""Gọi thẳng cổng LLM theo chuẩn OpenAI, không qua Codev.

Đường này đổi lấy hai thứ khác nhau. Được: số token chính xác tuyệt đối do
cổng báo, độ trễ thấp hơn, không phụ thuộc Codev, và chi phí cố định mỗi lượt
nhỏ hơn nhiều (qua Codev một lượt tốn sẵn khoảng 7.500 token cho system prompt
và định nghĩa tool). Mất: model không có tool nào, nên nó chỉ thấy đúng phần mã
mà `corpus.py` nhét vào đề bài — không tự đi đọc thêm được.

Chỉ dùng thư viện chuẩn, tương thích Python 3.9.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import metrics
from .codev import CodevError, Reply, extract_json

# Vai agent -> file prompt. Cung mot bo prompt voi duong Codev.
PROMPTS = {
    "aiscan-inventory": "scan-inventory.md",
    "aiscan-threat-model": "threat-model.md",
    "aiscan-researcher": "scan-researcher.md",
    "aiscan-sweep": "sweep.md",
    "aiscan-verifier": "scan-verifier.md",
    "aiscan-red-team": "red-team.md",
    "aiscan-explore": "explore.md",
}

# Nhiet do theo vai: vai phan quyet phai on dinh hon vai di tim.
TEMPERATURES = {
    "aiscan-researcher": 0.2,
    "aiscan-sweep": 0.2,
}
DEFAULT_TEMPERATURE = 0.1

RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


@dataclass
class DirectRunner:
    """Gọi cổng LLM tương thích OpenAI bằng HTTP thuần.

    Cùng giao diện `ask(agent, message) -> Reply` với `codev.Runner`, nên
    pipeline không cần biết đang chạy đường nào. `provides_tools` là chỗ khác
    biệt duy nhất pipeline phải hỏi.
    """

    base_url: str
    api_key: str
    model: str
    prompts_dir: Path
    timeout: int = 300
    max_tokens: int = 12000
    retries: int = 2
    provides_tools: bool = False
    _cache: dict[str, str] = field(default_factory=dict, repr=False)

    def system_for(self, agent: str) -> str:
        """Prompt hệ thống của một vai, đọc từ `prompts/` và nhớ lại."""
        if agent in self._cache:
            return self._cache[agent]
        name = PROMPTS.get(agent)
        if name is None:
            msg = f"khong biet vai {agent!r}; them vao PROMPTS trong direct.py"
            raise CodevError(msg)
        try:
            text = (self.prompts_dir / name).read_text(encoding="utf-8")
        except OSError as error:
            msg = f"khong doc duoc prompt cua {agent!r}: {error}"
            raise CodevError(msg) from error
        self._cache[agent] = text
        return text

    def payload(self, agent: str, message: str) -> dict[str, Any]:
        """Thân request gửi tới cổng."""
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_for(agent)},
                {"role": "user", "content": message},
            ],
            "temperature": TEMPERATURES.get(agent, DEFAULT_TEMPERATURE),
            "max_tokens": self.max_tokens,
        }

    def post(self, body: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Một request tới `/chat/completions`, có thử lại khi cổng bận."""
        url = self.base_url.rstrip("/") + "/chat/completions"
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        last = ""
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(url, data=data, headers=headers)  # noqa: S310
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as answer:  # noqa: S310
                    raw = answer.read().decode("utf-8", "replace")
                return json.loads(raw), raw
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", "replace")[:400]
                last = f"HTTP {error.code}: {detail}"
                if error.code not in RETRY_STATUS or attempt == self.retries:
                    raise CodevError(last) from error
            except (urllib.error.URLError, TimeoutError) as error:
                last = f"khong goi duoc cong: {error}"
                if attempt == self.retries:
                    raise CodevError(last) from error
            except ValueError as error:
                msg = f"cong tra ve thu khong phai JSON: {error}"
                raise CodevError(msg) from error
            # Lui dan: 2s, 6s.
            time.sleep(2 * (attempt + 1) ** 2 // 2 + 2 * attempt)
        raise CodevError(last)

    def ask(self, agent: str, message: str) -> Reply:
        """Gọi model cho một vai; CodevError khi hỏng hoặc không bóc được JSON."""
        started = time.monotonic()
        answer, raw = self.post(self.payload(agent, message))
        seconds = time.monotonic() - started

        if "error" in answer:
            msg = f"cong bao loi: {json.dumps(answer['error'])[:300]}"
            raise CodevError(msg)
        try:
            choice = answer["choices"][0]
            spoken = choice["message"]
        except (KeyError, IndexError, TypeError) as error:
            msg = f"cau tra loi thieu choices[0].message: {error}"
            raise CodevError(msg) from error

        # MiniMax M3 la model suy luan: no viet phan suy nghi vao
        # `reasoning_content`, va neu het han muc token khi con dang suy nghi
        # thi `content` ve rong. Lay tam phan suy luan de con boc duoc JSON.
        text = spoken.get("content") or spoken.get("reasoning_content") or ""
        if not text and choice.get("finish_reason") == "length":
            msg = (
                f"model het han muc {self.max_tokens} token khi dang suy luan, "
                "chua kip viet cau tra loi; tang --max-tokens"
            )
            raise CodevError(msg)

        reported = metrics.usage_of(answer)
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
            stdout=raw,
            seconds=seconds,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated=estimated,
        )
        try:
            data = extract_json(text)
        except CodevError as error:
            # Giu so do that: luot hong van da tieu token.
            raise CodevError(str(error), measured) from None
        return Reply(
            data=data,
            stdout=raw,
            seconds=seconds,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated=estimated,
        )
