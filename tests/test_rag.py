"""Unit tests for PHASE 4 RAG: conversations, citations, and answer generation."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from law_rag.rag.models import (
    Citation,
    CitationStatus,
    Conversation,
    Evidence,
    Message,
    MessageRole,
    RAGResponse,
)
from law_rag.rag.service import RAGService

NOW = datetime(2026, 9, 27, 11, 30, tzinfo=timezone.utc)


class ConversationTests(unittest.TestCase):
    def test_requires_conversation_id(self) -> None:
        with self.assertRaises(ValueError):
            Conversation.new(
                conversation_id="",
                user_id="u1",
            )

    def test_creates_conversation(self) -> None:
        conv = Conversation.new(
            conversation_id="conv1",
            user_id="u1",
            title="Legal Question",
        )

        self.assertEqual(conv.conversation_id, "conv1")
        self.assertFalse(conv.is_archived)


class MessageTests(unittest.TestCase):
    def test_requires_non_empty_content(self) -> None:
        with self.assertRaises(ValueError):
            Message.user_message(
                message_id="m1",
                conversation_id="conv1",
                content="   ",
            )

    def test_creates_user_message(self) -> None:
        msg = Message.user_message(
            message_id="m1",
            conversation_id="conv1",
            content="Quyết định 184/2024 quy định gì?",
        )

        self.assertTrue(msg.is_user_message)
        self.assertFalse(msg.is_assistant_message)
        self.assertEqual(msg.role, MessageRole.USER)

    def test_creates_assistant_message(self) -> None:
        msg = Message.assistant_message(
            message_id="m2",
            conversation_id="conv1",
            content="Quyết định 184/2024 quy định về...",
            trace_id="t1",
            as_of_date=date(2024, 12, 31),
        )

        self.assertFalse(msg.is_user_message)
        self.assertTrue(msg.is_assistant_message)
        self.assertEqual(msg.trace_id, "t1")


class EvidenceTests(unittest.TestCase):
    def test_requires_valid_score(self) -> None:
        with self.assertRaises(ValueError):
            Evidence(
                evidence_id="ev1",
                chunk_id="ch1",
                version_id="v1",
                document_number="184/2024/QĐ-TTg",
                document_title="Test",
                structural_path="Điều 1",
                content="Test content",
                page_start=1,
                page_end=1,
                score=1.5,
                is_verified=True,
                validity_status="in_force",
            )

    def test_creates_evidence_with_location(self) -> None:
        ev = Evidence(
            evidence_id="ev1",
            chunk_id="ch1",
            version_id="v1",
            document_number="184/2024/QĐ-TTg",
            document_title="Quyết định 184",
            structural_path="Chương I / Điều 1",
            content="Điều này quy định...",
            page_start=1,
            page_end=2,
            score=0.95,
            is_verified=True,
            validity_status="in_force",
        )

        self.assertTrue(ev.has_page_location)
        self.assertEqual(ev.page_start, 1)


class CitationTests(unittest.TestCase):
    def test_requires_non_empty_excerpt(self) -> None:
        with self.assertRaises(ValueError):
            Citation.new(
                citation_id="c1",
                message_id="m1",
                evidence_id="ev1",
                chunk_id="ch1",
                version_id="v1",
                document_number="184/2024/QĐ-TTg",
                document_title="Test",
                issuing_body="Thủ tướng",
                structural_path="Điều 1",
                excerpt="   ",
                page_start=1,
                page_end=1,
                source_spans=(),
                viewer_url="/viewer/v1?page=1",
                validity_status="in_force",
                as_of_date=date(2024, 12, 31),
            )

    def test_creates_valid_citation(self) -> None:
        citation = Citation.new(
            citation_id="c1",
            message_id="m1",
            evidence_id="ev1",
            chunk_id="ch1",
            version_id="v1",
            document_number="184/2024/QĐ-TTg",
            document_title="Quyết định 184",
            issuing_body="Thủ tướng Chính phủ",
            structural_path="Chương I / Điều 1",
            excerpt="Điều này quy định phạm vi áp dụng...",
            page_start=1,
            page_end=1,
            source_spans=("page:1/para:1",),
            viewer_url="/viewer/v1?page=1",
            validity_status="in_force",
            as_of_date=date(2024, 12, 31),
        )

        self.assertTrue(citation.is_valid)
        self.assertEqual(citation.status, CitationStatus.VALID)


class RAGResponseTests(unittest.TestCase):
    def test_requires_explanation_when_insufficient_evidence(self) -> None:
        with self.assertRaises(ValueError):
            RAGResponse(
                message_id="m1",
                answer="",
                evidence=(),
                citations=(),
                warnings=(),
                as_of_date=None,
                insufficient_evidence=True,
                trace_id="t1",
            )

    def test_creates_rag_response(self) -> None:
        evidence = Evidence(
            evidence_id="ev1",
            chunk_id="ch1",
            version_id="v1",
            document_number="184/2024/QĐ-TTg",
            document_title="Quyết định 184",
            structural_path="Điều 1",
            content="Content",
            page_start=1,
            page_end=1,
            score=0.95,
            is_verified=True,
            validity_status="in_force",
        )

        response = RAGResponse(
            message_id="m1",
            answer="Quyết định 184 quy định...",
            evidence=(evidence,),
            citations=(),
            warnings=(),
            as_of_date=date(2024, 12, 31),
            insufficient_evidence=False,
            trace_id="t1",
        )

        self.assertTrue(response.has_evidence)
        self.assertFalse(response.insufficient_evidence)


class RAGServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = RAGService()

    def test_creates_conversation(self) -> None:
        conv = self.service.create_conversation(
            user_id="u1",
            title="Legal Question",
        )

        self.assertIsNotNone(conv.conversation_id)
        self.assertEqual(conv.user_id, "u1")

    def test_adds_user_message(self) -> None:
        msg = self.service.add_user_message(
            conversation_id="conv1",
            content="Quyết định 184 quy định gì?",
        )

        self.assertEqual(msg.role, MessageRole.USER)
        self.assertEqual(msg.conversation_id, "conv1")

    def test_insufficient_evidence_response(self) -> None:
        response = self.service.generate_answer(
            question="Test question",
            evidence=[],
            user_id="u1",
        )

        self.assertTrue(response.insufficient_evidence)
        self.assertFalse(response.has_evidence)
        self.assertIn("không tìm thấy", response.answer.lower())

    def test_generates_answer_with_evidence(self) -> None:
        evidence = [
            Evidence(
                evidence_id="ev1",
                chunk_id="ch1",
                version_id="v1",
                document_number="184/2024/QĐ-TTg",
                document_title="Quyết định 184",
                structural_path="Điều 1",
                content="Điều này quy định phạm vi áp dụng của quyết định.",
                page_start=1,
                page_end=1,
                score=0.95,
                is_verified=True,
                validity_status="in_force",
            )
        ]

        response = self.service.generate_answer(
            question="Quyết định 184 quy định gì?",
            evidence=evidence,
            user_id="u1",
        )

        self.assertFalse(response.insufficient_evidence)
        self.assertTrue(response.has_evidence)
        self.assertTrue(response.has_citations)


if __name__ == "__main__":
    unittest.main()
