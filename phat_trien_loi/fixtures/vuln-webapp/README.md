# vuln-webapp — repo mẫu để thử AIScan

Một ứng dụng Flask nhỏ **cố ý cài lỗ hổng**, dùng làm bia tập bắn cho AIScan.

> **Cảnh báo.** Mã trong thư mục này chứa lỗ hổng có chủ đích. Không chạy, không
> triển khai, không sao chép sang dự án thật. Nó chỉ tồn tại để đo xem công cụ
> quét có tìm ra đúng những lỗi đã biết hay không.

## Cách dùng

    cd phat_trien_loi
    set -a && . ../.env && set +a
    python -m aiscan scan fixtures/vuln-webapp

## Chấm điểm

`expected.json` là đáp án: mỗi lỗi cố ý kèm file, dòng và CWE. Đáp án để riêng
chứ không viết vào mã — viết vào mã thì công cụ chỉ đọc nhãn, và con số
precision/recall trở nên vô nghĩa.

Đối chiếu báo cáo với đáp án:

- **Đúng (TP)**: một finding trùng file và CWE với một mục trong đáp án.
- **Báo nhầm (FP)**: finding không khớp mục nào.
- **Bỏ sót (FN)**: mục trong đáp án không có finding nào khớp.

Cũng nên xem cả những chỗ **không** có lỗi (`app/safe.py`): công cụ báo lỗi ở
đó là false positive rõ ràng.
