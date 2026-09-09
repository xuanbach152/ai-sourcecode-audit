"""Tải lên, tải xuống và xuất báo cáo."""

import os
import pickle
import subprocess

UPLOAD_DIR = "/var/app/uploads"
EXPORT_DIR = "/var/app/exports"


def read_upload(filename):
    """Đọc một file người dùng đã tải lên."""
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "rb") as handle:
        return handle.read()


def save_upload(filename, data):
    """Lưu file tải lên vào thư mục uploads."""
    path = os.path.join(UPLOAD_DIR, os.path.basename(filename))
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def convert_to_pdf(filename):
    """Chuyển một tài liệu sang PDF bằng công cụ dòng lệnh."""
    command = "libreoffice --headless --convert-to pdf " + filename
    return subprocess.check_output(command, shell=True)


def archive_exports(name):
    """Nén thư mục xuất báo cáo lại thành một file zip."""
    os.system("tar czf %s/%s.tar.gz %s" % (EXPORT_DIR, name, EXPORT_DIR))


def load_session_blob(blob):
    """Khôi phục trạng thái phiên client gửi kèm."""
    return pickle.loads(blob)


def cleanup(path):
    """Xoá một file tạm trong thư mục uploads."""
    target = os.path.realpath(os.path.join(UPLOAD_DIR, os.path.basename(path)))
    if not target.startswith(os.path.realpath(UPLOAD_DIR) + os.sep):
        raise ValueError("path outside upload directory")
    if os.path.isfile(target):
        os.remove(target)
