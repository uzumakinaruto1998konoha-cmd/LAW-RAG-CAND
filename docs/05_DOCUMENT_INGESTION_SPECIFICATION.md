# 05. Document Ingestion Specification

## 1. Đầu vào và giới hạn thiết kế v1
V1 nhận PDF (text, scan hoặc mixed), DOCX, JPG/PNG và plain text UTF-8; không nhận archive, macro-enabled Office, URL fetch hoặc batch archive. Giới hạn khởi điểm: 50 MiB/file, 500 trang PDF, 20 megapixel/ảnh; một job xử lý một file. Các giới hạn là cấu hình triển khai có giá trị mặc định, kiểm tra trước khi giải nén/parse và có thể hạ thấp theo môi trường. MIME được xác định từ nội dung/signature và đối chiếu extension; mismatch, encrypted PDF/DOCX, file hỏng, UTF-8 lỗi hoặc format không hỗ trợ bị quarantine/từ chối với mã lỗi ổn định. Giữ file gốc bất biến, hash SHA-256, tên gốc, uploader, thời gian, nguồn và ACL.

Parser/extractor v1: PyMuPDF 1.28.2 cho PDF text/page geometry; python-docx 1.2.0 cho DOCX; Pillow 12.3.0 cho ảnh; UTF-8 strict cho text. OCR cục bộ Tesseract 5.5.3 với `vie` traineddata chỉ chạy trên trang scan hoặc thiếu text layer (dưới 20 ký tự chữ/số hữu ích). Ghi tên/version tool, SHA-256 traineddata, cấu hình, confidence và page/span mapping vào kết quả processing. Các binary/model phải được đóng gói cục bộ; không gọi cloud. License: PyMuPDF AGPL v3 được chủ dự án chấp thuận cho triển khai nội bộ ngày 2026-09-26; python-docx MIT, Pillow MIT-CMU, Tesseract và model `tessdata_best` Apache-2.0. Phân phối ra ngoài phạm vi nội bộ phải rà soát license lại.

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
Tesseract 5.5.3 với `vie` là OCR cục bộ v1; confidence trang/vùng được lưu cùng engine, traineddata SHA-256, version và page mapping. Ngưỡng vận hành khởi điểm: OCR page mean confidence dưới 90/100, OCR không sinh text, hoặc parse/layout validation thất bại sẽ đặt document ở `review_required`; confidence không được diễn giải là xác suất đúng pháp lý. Luôn review khi tài liệu ảnh mờ/xoay hoặc có bảng/ghi chú tay mà mapping/thứ tự đọc không đạt kiểm tra cấu trúc. Mức 90 là ngưỡng định tuyến review, cần hiệu chỉnh bằng corpus được người duyệt xác nhận; không tự động approve theo confidence. Thiếu Tesseract/traineddata hoặc OCR lỗi cũng phải đưa vào review với mã cảnh báo, giữ file gốc.

DOCX chỉ có page number khi tài liệu có explicit/rendered page-break markers; nếu không, giữ locator theo paragraph/table/cell và để page number null vì Word pagination phụ thuộc renderer.

## 5.1 Legal parser v1
Parser v1 là rule-based, cấu hình được qua `LegalParseConfig` (không hard-code nội dung luật vào source; chỉ có từ khóa cấu trúc và từ vựng loại văn bản). Luồng: span đã trích xuất → ghép dòng theo thứ tự đọc (bbox cho PDF/OCR, locator cho DOCX/text) → dựng cây CHAPTER/SECTION/ARTICLE/CLAUSE/POINT/APPENDIX → trích metadata tối thiểu → nhận diện ứng viên quan hệ → định tuyến review.

Mỗi node, metadata assertion và relation candidate đều mang `source_locator`/`page_number`, `detector`, `confidence` (0-1) và mã cảnh báo ổn định; `raw_value` được giữ để đối chiếu nguyên văn. Confidence chỉ là tín hiệu định tuyến, không phải xác suất đúng pháp lý và không bao giờ tự duyệt tài liệu.

Ngưỡng định tuyến review khởi tạo: `review_confidence_threshold = 0.85` cho node/metadata; điểm/điều khoản nhận diện bằng danh sách đánh số (không nhãn) có confidence thấp hơn nên gần như luôn cần review. Cảnh báo ổn định: `HIERARCHY_NO_NODES`, `HIERARCHY_DUPLICATE_*`, `HIERARCHY_UNEXPECTED_ORDINAL_*`, `HIERARCHY_ORPHAN_MARKER`, `HIERARCHY_IMPLICIT_ORDINAL_*`, `METADATA_MISSING_*`, `METADATA_CONFLICT_*`, `METADATA_AMBIGUOUS_*`, `METADATA_INVALID_*`, `RELATION_TARGET_UNRESOLVED_*`; cảnh báo từ bước trích xuất (ví dụ `OCR_LOW_CONFIDENCE_PAGE_n`) được kế thừa. Ngày nhập dạng `dd/mm/yyyy` được chuẩn hóa ISO; ngày mơ hồ (tháng ≤ 12 và ngày ≤ 12) bị trừ confidence và cảnh báo.

Relation chỉ là ứng viên: mọi relation sinh ra ở trạng thái `unverified`, không tự sửa trạng thái hiệu lực. Reviewer phải accept/correct (kèm số/ký hiệu đích hoặc nhãn phạm vi đích) hoặc reject; relation `unverified` không được dùng làm nguồn hiệu lực. Chỉ khi mọi item yêu cầu xác minh đã xử lý và mọi warning đã được acknowledge thì reviewer mới duyệt; bản chưa duyệt không đủ điều kiện phát hành. Lưu ý vận hành: bộ rule v1 cần hiệu chỉnh trên corpus có quyền sử dụng trước khi mở rộng tự động hóa (ADR-006).

## 6. Corpus thiết kế v1 và phiên bản pipeline
Corpus acceptance được quản lý bằng manifest kiểm thử, không nhúng văn bản pháp luật vào source code. Manifest lưu mã mẫu, format/fixture hash, nhãn trang text/scan/mixed, hướng trang, ngôn ngữ, expected page count, expected text spans/metadata/hierarchy, expected review outcome và người duyệt. Bộ tối thiểu phải có PDF text, scan tiếng Việt có dấu (thẳng/xoay/mờ), PDF mixed, DOCX nhiều trang, JPG/PNG, UTF-8 text, file hỏng, MIME giả, file vượt giới hạn và bản exact-duplicate. Mẫu phải có quyền sử dụng, không chứa dữ liệu nhạy cảm chưa được phép; fixture pháp lý do chuyên gia cung cấp/duyệt, không tự tạo nội dung luật. Pipeline v1 gắn định danh `ingestion-v1`; đổi parser/OCR/config tạo processing run mới.

## 7. Lỗi và tái xử lý
Lưu mã lỗi có thể hành động, log có trace ID, không làm mất bản gốc. Tái xử lý tạo processing run/version mới và không âm thầm thay nội dung đã duyệt. Xóa/retention và quyền khôi phục cần chính sách TBD.
