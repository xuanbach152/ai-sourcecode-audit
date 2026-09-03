# Đồ án: Công cụ AI đánh giá ATTT source code

## Đề tài

Xây dựng công cụ/agent nội bộ dùng LLM đánh giá an toàn thông tin source code,
tích hợp vào GitLab (Codev). Tham khảo kiến trúc claude-security plugin
và claude-code-security-review.

## Vấn đề hiện tại

- SAST truyền thống (Fortify): tỉ lệ false positive cao, dev dần bỏ qua cảnh báo.
- Khó phát hiện lỗi phụ thuộc ngữ cảnh nghiệp vụ (phân quyền, logic, luồng đa module).
- Chưa có bộ tiêu chí + benchmark chuẩn để đo hiệu quả.

## Mục tiêu đầu ra

- Tool AI review code, hỗ trợ 2-3 ngôn ngữ chính nội bộ.
- Bộ prompt/rule theo OWASP Top 10 + CWE Top 25, có cơ chế tự kiểm chứng giảm FP.
- Tích hợp vào Codev (GitLab nội bộ).
- Báo cáo so sánh với Fortify: precision/recall, thời gian quét, chi phí token.
- Mã nguồn + tài liệu triển khai + hướng dẫn mở rộng rule.

## Repo tham khảo (clone về cùng cấp với folder này)

- `../claude-plugins-official/plugins/claude-security/`
  → kiến trúc multi-agent, SARIF 2.1.0, independent verifier.
- `../claude-code-security-review/`
  → prompt theo OWASP/CWE, false-positive filter, eval framework.

## Cấu trúc thư mục (theo timeline mentor)

| Folder                   | Tuần       | Nội dung                                                        |
| ------------------------ | ---------- | --------------------------------------------------------------- |
| `nghien_cuu_khao_sat/`   | W1         | Khảo sát hiện trạng, nghiên cứu 2 repo, viết báo cáo W1         |
| `thiet_ke/`              | W2         | Thiết kế kiến trúc, chọn ngôn ngữ, chọn LLM, chuẩn bị benchmark |
| `phat_trien_loi/`        | W3-W5      | Code lõi: PoC → engine đa ngôn ngữ → module giảm FP             |
| `tich_hop/`              | W6-W7      | Tích hợp GitLab CI/CD, MR comment, báo cáo quét                 |
| `kiem_thu_danh_gia/`     | W8-W9      | Benchmark Juliet/OWASP + so sánh Fortify, tối ưu                |
| `hoan_thien_nghiem_thu/` | W10-W11    | Tài liệu, thử nghiệm repo nội bộ, nghiệm thu                    |
| `_tham_khao/`            | suốt đồ án | Tài liệu, link, ghi chú tham khảo                               |

## Trạng thái hiện tại

- **Đang làm: W1 — Nghiên cứu & khảo sát**
- W1 deliverable: `nghien_cuu_khao_sat/bao_cao_W1.md`
- Hạn nộp W1: **06/09/2025**

## Ghi chú kỹ thuật (chốt sau W1-W2)

- LLM backend: on-prem qua LiteLLM proxy (cần chốt với mentor ở W2).
- Benchmark: Juliet Test Suite + OWASP Benchmark + 2-3 repo nội bộ.
- Ngôn ngữ ưu tiên: chốt sau khi khảo sát team.
- Output chuẩn: SARIF 2.1.0 (tích hợp GitLab Code Scanning).
