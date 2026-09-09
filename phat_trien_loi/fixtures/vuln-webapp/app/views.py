"""Các route HTTP của ứng dụng."""

from flask import Flask, redirect, request

from . import auth, db, files

app = Flask(__name__)


@app.route("/search")
def search():
    """Tìm người dùng theo tên."""
    name = request.args.get("name", "")
    rows = db.find_by_name(name)
    return {"results": rows}


@app.route("/admin/query")
def admin_query():
    """Tra cứu nâng cao cho trang quản trị."""
    field = request.args.get("field", "username")
    keyword = request.args.get("q", "")
    order = request.args.get("order", "id")
    return {"results": db.search(field, keyword, order)}


@app.route("/profile")
def profile():
    """Xem hồ sơ của một người dùng."""
    user_id = request.args.get("id")
    return {"profile": db.get_profile(user_id)}


@app.route("/greet")
def greet():
    """Trang chào mừng có kèm tên người dùng."""
    name = request.args.get("name", "khach")
    return "<h1>Xin chao " + name + "</h1><p>Chuc mot ngay tot lanh.</p>"


@app.route("/go")
def go():
    """Chuyển hướng người dùng sau khi đăng nhập."""
    target = request.args.get("next", "/")
    return redirect(target)


@app.route("/download")
def download():
    """Tải một file đã tải lên trước đó."""
    return files.read_upload(request.args.get("path", ""))


@app.route("/convert", methods=["POST"])
def convert():
    """Chuyển tài liệu sang PDF."""
    return files.convert_to_pdf(request.form["filename"])


@app.route("/session/restore", methods=["POST"])
def restore():
    """Khôi phục phiên từ dữ liệu client gửi lên."""
    return {"state": str(files.load_session_blob(request.get_data()))}


@app.route("/admin/users")
def admin_users():
    """Danh sách toàn bộ người dùng, chỉ dành cho quản trị."""
    claims = auth.read_token(request.headers.get("X-Token", ""))
    return {"users": db.search("role", "", "id"), "by": claims.get("sub")}


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
