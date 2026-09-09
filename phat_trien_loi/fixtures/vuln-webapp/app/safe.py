"""Các thao tác đã được viết đúng — dùng làm mồi thử false positive.

Không có lỗ hổng nào trong file này. Công cụ quét báo lỗi ở đây là báo nhầm.
"""

import hashlib
import hmac
import os
import secrets
import subprocess

ITERATIONS = 600_000


def hash_password(password, salt=None):
    """Băm mật khẩu bằng PBKDF2 với salt ngẫu nhiên."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return salt.hex() + "$" + digest.hex()


def verify_password(stored, password):
    """So khớp mật khẩu theo thời gian hằng định."""
    salt_hex, digest_hex = stored.split("$", 1)
    expected = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS
    )
    return hmac.compare_digest(expected.hex(), digest_hex)


def new_token():
    """Sinh token phiên bằng nguồn ngẫu nhiên an toàn."""
    return secrets.token_urlsafe(32)


def list_directory(root, name):
    """Liệt kê một thư mục con, chặn mọi đường dẫn thoát ra ngoài root."""
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, name))
    if target != base and not target.startswith(base + os.sep):
        raise ValueError("path escapes the root directory")
    return sorted(os.listdir(target))


def run_checker(path):
    """Gọi công cụ kiểm tra, truyền tham số dạng mảng nên shell không diễn giải."""
    return subprocess.run(
        ["/usr/bin/checker", "--file", path],
        capture_output=True,
        check=False,
        shell=False,
    ).stdout
