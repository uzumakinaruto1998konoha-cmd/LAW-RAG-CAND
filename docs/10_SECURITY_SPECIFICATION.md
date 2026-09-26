# 10. Security Specification

## 1. Mục tiêu
Bảo vệ tài liệu nội bộ và dữ liệu hội thoại; thực thi least privilege, có audit và vận hành LAN/offline. Chi tiết threat model, retention và tiêu chuẩn tuân thủ TBD.

## 2. RBAC
Vai trò khởi điểm đề xuất: System Admin, Knowledge Admin, Reviewer, User, Auditor. Quyền phải tách upload, xem, sửa metadata, duyệt/phát hành, xóa/archival, quản lý user/role, truy vấn, xem audit và quản trị index. Role/permission matrix cần chủ dự án duyệt. Hỗ trợ ACL tài liệu/collection nếu có dữ liệu giới hạn.

## 3. Kiểm soát
- AuthN, session/token, mật khẩu/MFA/SSO, lockout và vòng đời tài khoản: TBD.
- AuthZ server-side ở API, retrieval, citation viewer, file download, export và tác vụ nền.
- Mã hóa truyền tải trong LAN và mã hóa lưu trữ: chính sách/certificate/key management TBD.
- Validate upload, giới hạn tài nguyên, chống path traversal, parser isolation và xử lý prompt injection từ tài liệu.
- Không ghi secrets, nội dung nhạy cảm hoặc prompt đầy đủ vào log mặc định.
- Secret qua biến/mount an toàn khi triển khai; không hard-code hoặc commit.

## 4. Audit
Ghi actor, action, object, timestamp, outcome, trace ID, nguồn client phù hợp; audit upload, duyệt, sửa/xóa, thay role, truy vấn quản trị, rebuild/restore. Quy tắc ghi truy vấn/chat và thời hạn lưu TBD; log chống sửa/xóa TBD.

## 5. Threats
Tài liệu độc hại, OCR/parser exploit, prompt injection, rò rỉ qua retrieval, quyền sai ở citation/download, tài khoản bị chiếm, backup bị lộ, mất điện/hỏng ổ đĩa, model/log lưu dữ liệu ngoài ý muốn.

## 6. Backup/restore và sự cố
Backup mã hóa/kiểm soát quyền, tách bản sao khỏi host khi chính sách cho phép; kiểm thử restore định kỳ. RPO/RTO, lịch, retention, nơi lưu và quy trình sự cố TBD. LAN không đồng nghĩa tin cậy toàn bộ client.
