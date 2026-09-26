# 05. Document Ingestion Specification

## 1. Đầu vào và giới hạn thiết kế v1
V1 nhận PDF (text, scan hoặc mixed), DOCX, JPG/PNG và plain text UTF-8; không nhận archive, macro-enabled Office, URL fetch hoặc batch archive. Giới hạn khởi điểm: 50 MiB/file, 500 trang PDF, 20 megapixel/ảnh; một job xử lý một file. Các giới hạn là cấu hình triển khai có giá trị mặc định, kiểm tra trước khi giải nén/parse và có thể hạ thấp theo môi trường. MIME được xác định từ nội dung/signature và đối chiếu extension; mismatch, encrypted PDF/DOCX, file hỏng, UTF-8 lỗi hoặc format không hỗ trợ bị quarantine/từ chối với mã lỗi ổn định. Giữ file gốc bất biến, hash SHA-256, tên gốc, uploader, thời gian, nguồn và ACL.

Parser/extractor v1: PyMuPDF cho PDF text/page geometry; python-docx cho DOCX; Pillow cho ảnh; UTF-8 strict cho text. OCR cục bộ Tesseract 5.x với Vietnamese `vie` traineddata chỉ chạy trên trang thiếu text layer/chất lượng text thấp. Ghi tên và phiên bản tool, traineddata, cấu hình, confidence và page/span mapping vào processing run. Các binary/model phải được đóng gói cục bộ; không gọi cloud. Đây là dependency design cho task triển khai kế tiếp, chưa thêm package hay binary vào repo trong task thiết kế này.

Blob gốc và artefact đặt trong persistent filesystem volume riêng, tên nội bộ dựa trên content hash; không dùng tên upload làm path. PostgreSQL lưu metadata, job và storage key; file ghi tạm trong quarantine, xác minh xong mới promote nguyên tử sang khu lưu trữ. Backup phải bao gồm blob volume cùng PostgreSQL. Không bật malware scanner ở v1 nếu chưa có engine cục bộ được duyệt; file vẫn bị giới hạn, signature-check và xử lý trong worker cách ly.

## 2. Các bước
1. Upload vào vùng cách ly; xác minh extension/MIME/signature và kích thước theo giới hạn v1. Không tuyên bố malware-scanning; xử lý trong worker cách ly.
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
Tesseract 5.x với `vie` là OCR cục bộ v1; confidence trang/vùng được lưu cùng engine, traineddata, version và page mapping. Ngưỡng vận hành khởi điểm: OCR page mean confidence dưới 90/100, OCR không sinh text, hoặc parse/layout validation thất bại sẽ đặt document ở `review_required`; confidence không được diễn giải là xác suất đúng pháp lý. Luôn review khi tài liệu ảnh mờ/xoay hoặc có bảng/ghi chú tay mà mapping/thứ tự đọc không đạt kiểm tra cấu trúc. Mức 90 là ngưỡng định tuyến review, cần hiệu chỉnh bằng corpus được người duyệt xác nhận; không tự động approve theo confidence.

## 6. Corpus thiết kế v1 và phiên bản pipeline
Corpus acceptance được quản lý bằng manifest kiểm thử, không nhúng văn bản pháp luật vào source code. Manifest lưu mã mẫu, format/fixture hash, nhãn trang text/scan/mixed, hướng trang, ngôn ngữ, expected page count, expected text spans/metadata/hierarchy, expected review outcome và người duyệt. Bộ tối thiểu phải có PDF text, scan tiếng Việt có dấu (thẳng/xoay/mờ), PDF mixed, DOCX nhiều trang, JPG/PNG, UTF-8 text, file hỏng, MIME giả, file vượt giới hạn và bản exact-duplicate. Mẫu phải có quyền sử dụng, không chứa dữ liệu nhạy cảm chưa được phép; fixture pháp lý do chuyên gia cung cấp/duyệt, không tự tạo nội dung luật. Pipeline v1 gắn định danh `ingestion-v1`; đổi parser/OCR/config tạo processing run mới.

## 7. Lỗi và tái xử lý
Lưu mã lỗi có thể hành động, log có trace ID, không làm mất bản gốc. Tái xử lý tạo processing run/version mới và không âm thầm thay nội dung đã duyệt. Xóa/retention và quyền khôi phục cần chính sách TBD.
