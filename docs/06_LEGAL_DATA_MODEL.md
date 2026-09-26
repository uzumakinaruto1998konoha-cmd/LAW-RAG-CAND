# 06. Legal Data Model

## 1. Nguyên tắc
PostgreSQL là nguồn chuẩn. Dữ liệu pháp lý có thời gian hiệu lực (valid time) và thời gian hệ thống ghi nhận (transaction time). Không ghi đè lịch sử; mọi quan hệ và trạng thái có nguồn, confidence, xác minh.

## 2. Entitas đề xuất
- `User`, `Role`, `Permission`, `UserRole`, `RolePermission`; `AuditEvent`.
- `Document`: danh tính logic/loại nguồn/phân loại.
- `DocumentVersion`: phiên bản phát hành/nhập, số hiệu, tiêu đề, cơ quan, ngày tháng, hash, trạng thái duyệt/hiệu lực, source provenance.
- `FileAsset`: bản gốc và artefact dẫn xuất; storage key, MIME, size, hash.
- `Page`/`SourceSpan`: số trang, text, bounding box/offset, phương pháp trích xuất, confidence.
- `LegalNode`: cây cấu trúc CHAPTER/SECTION/ARTICLE/CLAUSE/POINT, nhãn, số thứ tự, nội dung, parent, span.
- `MetadataAssertion`: trường, giá trị, nguồn, confidence, người duyệt, thời điểm.
- `DocumentRelation`: source version, target version/node, loại relation, phạm vi điều khoản, valid dates, nguồn và trạng thái xác minh.
- `ProcessingRun`, `IngestionJob`, `ChunkSet`, `Chunk`, `IndexManifest`.
- `Conversation`, `Message`, `RetrievalTrace`, `Citation` (retention/privacy TBD).

## 3. Quan hệ pháp lý
Enum ban đầu: AMENDS, SUPPLEMENTS, REPLACES, REPEALS, GUIDES, REFERENCES. Relation cần hướng rõ, có thể giới hạn ở toàn văn bản hoặc điều/khoản, và ngày hiệu lực. Relation không xác minh chỉ tạo cảnh báo/ứng viên, không tự sửa trạng thái hiệu lực.

## 4. Hiệu lực
Không dùng một boolean duy nhất. Lưu các mốc ngày và trạng thái khai báo; tính hiệu lực tại `as_of_date` từ dữ liệu xác minh và quan hệ đã duyệt. Trạng thái đề xuất: UNKNOWN, NOT_YET_EFFECTIVE, IN_FORCE, PARTIALLY_EFFECTIVE, AMENDED, REPEALED, EXPIRED, CONFLICT. Quy tắc xác định và xử lý văn bản một phần hiệu lực TBD.

## 5. Chỉ mục và khóa
Mọi chunk tham chiếu version, node, page/span và ACL scope. Unique constraints cần quyết định cho số/ký hiệu + cơ quan + loại văn bản; không giả định số hiệu là duy nhất toàn cục. Xóa ưu tiên soft-delete/archival; retention TBD.

## 6. Vấn đề cần thiết kế chi tiết
Lược đồ đa ngôn ngữ; biểu diễn văn bản hợp nhất; amendment overlay; ACL theo document/collection; chuẩn hóa cơ quan/loại văn bản; ngày không rõ; trích dẫn ngoài kho. Xem Decision Log.
