"""Nạp văn bản pháp luật mẫu vào kho tri thức để hệ thống có dữ liệu hoạt động ngay lập tức.

Các văn bản được đưa qua Ingestion Pipeline:
Trích xuất -> Bóc tách Chương/Điều/Khoản -> Phê duyệt phát hành -> Chia Chunk -> Lập chỉ mục.
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from law_rag.api.container import ApiContainer

LOGGER = logging.getLogger(__name__)

DOC_TRAFFC = """Luật số: 36/2024/QH15
Cơ quan ban hành: Quốc hội
Ngày ban hành: 27 tháng 06 năm 2024
Có hiệu lực từ: 01 tháng 01 năm 2025
LUẬT TRẬT TỰ, AN TOÀN GIAO THÔNG ĐƯỜNG BỘ

Chương I. QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Luật này quy định về quy tắc, phương tiện, người tham gia giao thông đường bộ, chỉ huy, điều khiển, tuần tra, kiểm soát, xử lý vi phạm pháp luật về trật tự, an toàn giao thông đường bộ, giải quyết tai nạn giao thông đường bộ; trách nhiệm quản lý nhà nước về trật tự, an toàn giao thông đường bộ.

Điều 2. Đối tượng áp dụng
1. Cơ quan, tổ chức, cá nhân liên quan đến trật tự, an toàn giao thông đường bộ trên lãnh thổ nước Cộng hòa xã hội chủ nghĩa Việt Nam.

Điều 9. Các hành vi bị nghiêm cấm
1. Điều khiển phương tiện tham gia giao thông đường bộ mà trong máu hoặc hơi thở có nồng độ cồn.
2. Điều khiển phương tiện tham gia giao thông đường bộ mà trong cơ thể có chất ma túy hoặc chất kích thích khác mà pháp luật cấm sử dụng.
3. Điều khiển phương tiện tham gia giao thông đường bộ không có giấy phép lái xe theo quy định của pháp luật.
4. Đua xe, cổ vũ đua xe, tổ chức đua xe trái phép, lạng lách, đánh võng.
5. Giao xe cơ giới, xe máy chuyên dùng cho người không đủ điều kiện theo quy định của pháp luật để điều khiển tham gia giao thông đường bộ.

Chương II. TUẦN TRA, KIỂM SOÁT VÀ XỬ LÝ VI PHẠM

Điều 65. Thẩm quyền tuần tra, kiểm soát của Cảnh sát giao thông
1. Cảnh sát giao thông thuộc Công an nhân dân thực hiện tuần tra, kiểm soát để bảo đảm trật tự, an toàn giao thông đường bộ.
2. Dừng phương tiện tham gia giao thông đường bộ để kiểm soát người, phương tiện, hàng hóa theo quy định của pháp luật.
3. Xử lý vi phạm hành chính về trật tự, an toàn giao thông đường bộ theo quy định của pháp luật về xử lý vi phạm hành chính.
"""

DOC_IDENTITY = """Luật số: 26/2023/QH15
Cơ quan ban hành: Quốc hội
Ngày ban hành: 27 tháng 11 năm 2023
Có hiệu lực từ: 01 tháng 07 năm 2024
LUẬT CĂN CƯỚC

Chương I. QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Luật này quy định về Cơ sở dữ liệu quốc gia về dân cư, Cơ sở dữ liệu căn cước; thẻ căn cước, căn cước điện tử; giấy chứng nhận căn cước; quyền, nghĩa vụ, trách nhiệm của cơ quan, tổ chức, cá nhân có liên quan.

Điều 3. Giải thích từ ngữ
1. Căn cước là thông tin cơ bản về nhân thân, lai lịch, nhân dạng và sinh trắc học của một người.
2. Thẻ căn cước là giấy tờ tùy thân chứa đựng thông tin về căn cước của công dân Việt Nam, do cơ quan quản lý căn cước cấp theo quy định của Luật này.
3. Căn cước điện tử là căn cước của công dân Việt Nam được thể hiện qua tài khoản định danh điện tử do hệ thống định danh và xác thực điện tử tạo lập.

Điều 19. Người được cấp thẻ căn cước
1. Công dân Việt Nam từ đủ 14 tuổi trở lên phải thực hiện thủ tục cấp thẻ căn cước.
2. Công dân Việt Nam dưới 14 tuổi được cấp thẻ căn cước theo nhu cầu.

Chương II. TRÁCH NHIỆM QUẢN LÝ NHÀ NƯỚC

Điều 46. Trách nhiệm của Bộ Công an
1. Bộ Công an là cơ quan đầu mối giúp Chính phủ thực hiện quản lý nhà nước về căn cước, Cơ sở dữ liệu quốc gia về dân cư và Cơ sở dữ liệu căn cước.
2. Xây dựng, quản lý và vận hành hệ thống sản xuất, cấp và quản lý thẻ căn cước, căn cước điện tử bảo đảm an ninh, an toàn thông tin.
"""


def seed_sample_corpus(container: ApiContainer) -> int:
    """Nạp văn bản pháp luật mẫu vào kho tri thức qua pipeline."""
    if not container.pipeline:
        return 0

    count = 0
    admin_user = container.user("u_admin") or container.user("u_system")
    reviewer_user = container.user("u_reviewer") or admin_user
    if not admin_user or not reviewer_user:
        return 0

    documents = [
        ("luat_trat_tu_an_toan_giao_thong_36_2024.txt", DOC_TRAFFC, "coll_public", "seed_traffic_2024"),
        ("luat_can_cuoc_26_2023.txt", DOC_IDENTITY, "coll_cand_internal", "seed_identity_2023"),
    ]

    for filename, content, collection_id, key in documents:
        try:
            receipt = container.ingestion_service.upload(
                filename=filename,
                stream=io.BytesIO(content.encode("utf-8")),
                idempotency_key=key,
                uploader_id=admin_user.user_id,
                source="seed_corpus",
            )
            job_id = receipt.job.job_id
            outcome = container.pipeline.process(job_id)

            from law_rag.ingestion.legal_review import (
                ReviewAction,
                ReviewDecision,
                ReviewItemKind,
                pending_tasks,
            )
            latest = container.pipeline.legal_repository.get_latest(job_id)
            if latest:
                tasks = pending_tasks(latest)
                if tasks:
                    decisions = [
                        ReviewDecision(
                            item_kind=t.item_kind,
                            item_id=t.item_id,
                            action=ReviewAction.REJECT if t.item_kind == ReviewItemKind.RELATION else ReviewAction.ACCEPT,
                            reviewer_id=reviewer_user.user_id,
                        )
                        for t in tasks
                    ]
                    container.pipeline.submit_decisions(job_id, decisions)


            container.pipeline.approve(
                job_id,
                reviewer_id=reviewer_user.user_id,
                acknowledged_warnings=outcome.warnings,
                released_by=reviewer_user.user_id,
                collection_id=collection_id,
            )
            count += 1
            LOGGER.info("Seeded sample document: %s into collection %s", filename, collection_id)
        except Exception as exc:
            LOGGER.warning("Could not seed %s: %s", filename, exc)

    return count

