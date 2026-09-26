# 05. Document Ingestion Specification

## 1. Đầu vào
PDF có text, PDF scan/mixed, DOCX, JPG/PNG và plain text. Giới hạn kích thước/trang, MIME thực, mã hóa text, batch upload và định dạng khác TBD. Giữ file gốc bất biến, hash SHA-256, tên gốc, uploader, thời gian, nguồn và ACL.

## 2. Các bước
1. Upload vào vùng cách ly; xác minh extension/MIME/signature, kích thước, malware scanning capability TBD.
2. Tạo hồ sơ upload, hash và phát hiện trùng exact; ứng viên near-duplicate được cảnh báo, không tự gộp.
3. Nhận diện text layer/chất lượng trang; OCR trang cần thiết, lưu engine/version/confidence và mapping trang.
4. Trích xuất text theo thứ tự đọc, giữ page breaks và tọa độ khi khả dụng.
5. Chuẩn hóa khoảng trắng/ký tự nhưng bảo toàn nguyên văn nguồn và provenance; mọi thay đổi có thể truy ngược.
6. Parse metadata, cấu trúc Chương/Mục/Điều/Khoản/Điểm và quan hệ với confidence.
7. Review thủ công, sửa trường, duyệt; lưu người duyệt và thời điểm.
8. Chỉ bản được duyệt mới đủ điều kiện phát hành vào retrieval; chunk/embed/index với pipeline version.

## 3. Trạng thái job
`uploaded`, `quarantined`, `queued`, `extracting`, `ocr`, `parsing`, `review_required`, `approved`, `indexing`, `indexed`, `failed`, `superseded`, `archived`. Trạng thái chuyển tiếp, retry/idempotency, hủy job và xóa dữ liệu TBD ở thiết kế chi tiết.

## 4. Metadata tối thiểu
Loại tài liệu/nguồn; tiêu đề; số/ký hiệu; cơ quan ban hành; ngày ban hành; ngày hiệu lực; ngày hết hiệu lực; trạng thái; lĩnh vực; ngôn ngữ; nguồn/URL hoặc hồ sơ nhập; phiên bản/quan hệ; trạng thái xác minh; độ tin cậy; mã băm; file/page locator; phân loại bảo mật và ACL.

## 5. OCR và chất lượng
OCR cục bộ, hỗ trợ tiếng Việt và dấu; engine/model/version TBD. Ghi confidence trang/vùng; ngưỡng đưa vào review TBD. Trang xoay, mờ, bảng, dấu/ghi chú tay phải được kiểm thử; không tự coi OCR text là chuẩn khi chất lượng thấp.

## 6. Lỗi và tái xử lý
Lưu mã lỗi có thể hành động, log có trace ID, không làm mất bản gốc. Tái xử lý tạo processing run/version mới và không âm thầm thay nội dung đã duyệt. Xóa/retention và quyền khôi phục cần chính sách TBD.
