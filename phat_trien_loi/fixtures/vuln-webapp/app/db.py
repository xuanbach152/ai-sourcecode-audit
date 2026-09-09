"""Truy cập cơ sở dữ liệu người dùng."""

import sqlite3

DB_PATH = "users.db"


def connect():
    return sqlite3.connect(DB_PATH)


def find_by_name(name):
    """Tìm người dùng theo tên."""
    conn = connect()
    cursor = conn.cursor()
    sql = "SELECT id, username, email, role FROM users WHERE username = '" + name + "'"
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()
    return rows


def search(field, keyword, order):
    """Tìm kiếm linh hoạt theo cột và thứ tự sắp xếp do người gọi chọn."""
    conn = connect()
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE %s LIKE '%%%s%%' ORDER BY %s" % (field, keyword, order)
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_profile(user_id):
    """Lấy hồ sơ theo id."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, phone FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def update_email(user_id, email):
    """Cập nhật email cho một người dùng."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
    conn.commit()
    conn.close()
