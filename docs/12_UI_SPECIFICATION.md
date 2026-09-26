# 12. UI Specification

## 1. Khu vực
- Tra cứu/chat: câu hỏi, ngày áp dụng, filter, câu trả lời, căn cứ, cảnh báo, link trang PDF.
- Kết quả tìm kiếm: metadata, trạng thái hiệu lực, cấu trúc pháp lý, nguồn nội bộ/pháp luật.
- Kho tri thức: danh sách, chi tiết, phiên bản, timeline hiệu lực, quan hệ, ACL.
- Ingestion/review: upload, tiến độ, preview trang/text, OCR confidence, cây cấu trúc, sửa metadata/quan hệ, duyệt/từ chối.
- Quản trị: users/roles, audit, index manifests, backup/restore trạng thái theo quyền.

## 2. Hành vi quan trọng
Thể hiện rõ ngày tra cứu, trạng thái xác minh, cảnh báo mâu thuẫn/hết hiệu lực, confidence OCR và trạng thái “không đủ căn cứ”. Citation mở đúng phiên bản/trang. Không hiển thị nội dung nếu ACL không cho phép. Thao tác duyệt/sửa/xóa cần xác nhận và audit.

## 3. Trạng thái giao diện
Loading, empty, error, partial/OCR, permission denied, stale index, failed job, insufficient evidence và conflict phải có cách trình bày rõ ràng. Không biểu diễn “không tìm thấy” như “không tồn tại trong pháp luật”.

## 4. Accessibility và ngôn ngữ
Ưu tiên tiếng Việt; ngày/giờ và Unicode chuẩn; bàn phím, nhãn biểu mẫu và tương phản cần nghiệm thu. Responsive desktop trước hay mobile parity TBD.

## 5. Vai trò
Ẩn/khóa chức năng theo quyền ở UI nhưng backend vẫn là nơi quyết định cuối cùng. Ma trận màn hình-quyền TBD cùng RBAC.
