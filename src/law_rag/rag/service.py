"""RAG service for PHASE 4: Grounded answer generation with local LLM."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from .models import Citation, Conversation, Evidence, Message, MessageRole, RAGResponse

if TYPE_CHECKING:
    from datetime import date

LOGGER = logging.getLogger(__name__)


class InsufficientEvidenceError(Exception):
    """Raised when retrieved evidence is insufficient to answer the question."""
    pass


class RAGService:
    """Generate grounded legal answers using retrieved evidence and local LLM.
    
    Per docs/04: Answers must be grounded in approved evidence with citations.
    No hallucination: citations are server-generated from evidence IDs only.
    """

    def __init__(self) -> None:
        # In production, would inject LLM client (Ollama), retrieval service, etc.
        pass

    def generate_answer(
        self,
        *,
        question: str,
        evidence: list[Evidence],
        as_of_date: date | None = None,
        user_id: str,
        conversation_id: str | None = None,
    ) -> RAGResponse:
        """Generate grounded answer from retrieved evidence.
        
        Per docs/04 section 3-4:
        1. Create labeled context from evidence
        2. Require model to synthesize only within evidence bounds
        3. Check citations against evidence IDs
        4. Detect insufficient evidence and warn
        """
        # Check evidence sufficiency
        if not evidence or len(evidence) < 1:
            return self._insufficient_evidence_response(
                question=question,
                reason="Không tìm thấy tài liệu pháp lý phù hợp trong cơ sở dữ liệu.",
                as_of_date=as_of_date,
            )

        # Build context from evidence
        context_parts = []
        for idx, ev in enumerate(evidence, 1):
            context_parts.append(
                f"[Nguồn {idx}] {ev.document_title} - {ev.structural_path}\n{ev.content}"
            )
        
        context = "\n\n".join(context_parts)

        # Generate answer (placeholder - would call Ollama LLM)
        # In production: send context + question to local LLM with strict prompt
        answer = self._generate_with_llm(question, context, evidence)

        # Generate citations from evidence (server-side only)
        citations = self._generate_citations(
            evidence=evidence,
            message_id=f"msg_{uuid.uuid4().hex[:16]}",
            as_of_date=as_of_date,
        )

        # Check for validity warnings
        warnings = self._check_warnings(evidence, as_of_date)

        message_id = f"msg_{uuid.uuid4().hex[:16]}"
        trace_id = f"trace_{uuid.uuid4().hex[:16]}"

        return RAGResponse(
            message_id=message_id,
            answer=answer,
            evidence=tuple(evidence),
            citations=tuple(citations),
            warnings=tuple(warnings),
            as_of_date=as_of_date,
            insufficient_evidence=False,
            trace_id=trace_id,
        )

    def _generate_with_llm(
        self,
        question: str,
        context: str,
        evidence: list[Evidence],
    ) -> str:
        """Call local LLM to generate grounded answer.
        
        In production, would use Ollama API with prompt template:
        - System: You are a legal research assistant. Only use provided evidence.
        - Context: [numbered evidence chunks]
        - Question: [user question]
        - Instruction: Answer based only on provided sources. Cite [Nguồn N].
        """
        # Placeholder implementation
        answer = f"Dựa trên các tài liệu pháp lý được tìm thấy:\n\n"
        
        # Simulate grounded answer generation
        if evidence:
            first_ev = evidence[0]
            answer += f"Theo {first_ev.document_title}, {first_ev.structural_path}: "
            answer += f"{first_ev.content[:200]}..."
            
        answer += "\n\n[Lưu ý: Đây là câu trả lời mẫu. Triển khai thực tế sẽ tích hợp Ollama.]"
        
        return answer

    def _generate_citations(
        self,
        evidence: list[Evidence],
        message_id: str,
        as_of_date: date | None,
    ) -> list[Citation]:
        """Generate server-side citations from evidence.
        
        Per docs/09 section 3: Server generates citations from evidence IDs only.
        LLM does not provide citation data directly.
        """
        citations = []
        
        for ev in evidence[:5]:  # Top 5 evidence items
            citation_id = f"cite_{uuid.uuid4().hex[:16]}"
            
            # Extract excerpt (first 200 chars or full content)
            excerpt = ev.content[:200] + "..." if len(ev.content) > 200 else ev.content
            
            # Build viewer URL
            viewer_url = None
            if ev.page_start:
                viewer_url = f"/viewer/{ev.version_id}?page={ev.page_start}"
            
            citation = Citation.new(
                citation_id=citation_id,
                message_id=message_id,
                evidence_id=f"ev_{uuid.uuid4().hex[:16]}",
                chunk_id=ev.chunk_id,
                version_id=ev.version_id,
                document_number=ev.document_number,
                document_title=ev.document_title,
                issuing_body=None,  # Would fetch from document metadata
                structural_path=ev.structural_path,
                excerpt=excerpt,
                page_start=ev.page_start,
                page_end=ev.page_end,
                source_spans=(),
                viewer_url=viewer_url,
                validity_status=ev.validity_status,
                as_of_date=as_of_date,
            )
            citations.append(citation)
        
        return citations

    def _check_warnings(
        self,
        evidence: list[Evidence],
        as_of_date: date | None,
    ) -> list[str]:
        """Generate warnings about answer limitations.
        
        Per docs/04 section 5: Warn about conflicts, unverified relations, etc.
        """
        warnings = []
        
        # Check for unverified evidence
        unverified_count = sum(1 for ev in evidence if not ev.is_verified)
        if unverified_count > 0:
            warnings.append(
                f"Có {unverified_count} tài liệu chưa được xác minh đầy đủ."
            )
        
        # Check for validity status
        unknown_validity = [ev for ev in evidence if ev.validity_status == "unknown"]
        if unknown_validity:
            warnings.append(
                "Một số tài liệu chưa xác định rõ trạng thái hiệu lực."
            )
        
        # Check as_of_date
        if not as_of_date:
            warnings.append(
                "Truy vấn không chỉ định ngày áp dụng cụ thể. Kết quả dựa trên ngày hiện tại."
            )
        
        return warnings

    def _insufficient_evidence_response(
        self,
        question: str,
        reason: str,
        as_of_date: date | None,
    ) -> RAGResponse:
        """Generate response when evidence is insufficient.
        
        Per docs/04 section 4: Must indicate insufficient evidence clearly.
        """
        message_id = f"msg_{uuid.uuid4().hex[:16]}"
        trace_id = f"trace_{uuid.uuid4().hex[:16]}"
        
        answer = (
            f"Xin lỗi, tôi không tìm thấy đủ căn cứ pháp lý trong cơ sở dữ liệu "
            f"để trả lời câu hỏi của bạn.\n\n"
            f"Lý do: {reason}\n\n"
            f"Gợi ý: Bạn có thể thử:\n"
            f"- Diễn đạt câu hỏi khác đi\n"
            f"- Sử dụng từ khóa cụ thể hơn\n"
            f"- Kiểm tra lại phạm vi tìm kiếm"
        )
        
        return RAGResponse(
            message_id=message_id,
            answer=answer,
            evidence=(),
            citations=(),
            warnings=(
                "Không tìm thấy tài liệu liên quan trong cơ sở dữ liệu.",
            ),
            as_of_date=as_of_date,
            insufficient_evidence=True,
            trace_id=trace_id,
        )

    def create_conversation(
        self,
        *,
        user_id: str,
        title: str | None = None,
    ) -> Conversation:
        """Create new conversation for user."""
        conversation_id = f"conv_{uuid.uuid4().hex[:16]}"
        return Conversation.new(
            conversation_id=conversation_id,
            user_id=user_id,
            title=title,
        )

    def add_user_message(
        self,
        *,
        conversation_id: str,
        content: str,
        as_of_date: date | None = None,
    ) -> Message:
        """Add user message to conversation."""
        message_id = f"msg_{uuid.uuid4().hex[:16]}"
        return Message.user_message(
            message_id=message_id,
            conversation_id=conversation_id,
            content=content,
            as_of_date=as_of_date,
        )

    def validate_citation(
        self,
        citation: Citation,
        user_id: str,
    ) -> bool:
        """Validate citation before returning to user.
        
        Per docs/09 section 4: Check ID exists, user has permission, content matches.
        """
        # In production: check version exists, user ACL, content span matches
        # For now, placeholder validation
        return citation.is_valid
