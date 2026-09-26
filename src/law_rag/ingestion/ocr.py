"""Local Tesseract OCR adapter with TSV confidence and word coordinates."""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

from .errors import ExtractionError, OCRUnavailableError
from .validation import MAX_IMAGE_PIXELS

LOGGER = logging.getLogger(__name__)
OCR_TIMEOUT_SECONDS = 120


@dataclass(frozen=True, slots=True)
class OCRWord:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class OCRResult:
    words: tuple[OCRWord, ...]
    mean_confidence: float
    tool_versions: tuple[tuple[str, str], ...]


class OCRProcessor(Protocol):
    def recognize(self, image_bytes: bytes) -> OCRResult: ...


class TesseractOCR:
    def __init__(
        self,
        *,
        executable: str = "tesseract",
        language: str = "vie",
        timeout_seconds: int = OCR_TIMEOUT_SECONDS,
    ) -> None:
        if not language.isalpha() or timeout_seconds <= 0:
            raise ValueError("Invalid OCR language or timeout")
        self.executable = executable
        self.language = language
        self.timeout_seconds = timeout_seconds
        self._version: str | None = None
        self._resolved_executable: str | None = None
        self._traineddata_digest: str | None = None

    def _verify(self) -> str:
        if self._resolved_executable is not None:
            return self._resolved_executable
        executable = shutil.which(self.executable)
        if executable is None:
            raise OCRUnavailableError("Local Tesseract executable is unavailable")
        try:
            version = subprocess.run([executable, "--version"], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
            languages = subprocess.run([executable, "--list-langs"], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OCRUnavailableError("Local Tesseract could not be started") from exc
        first_line = version.stdout.splitlines()[0] if version.stdout else ""
        if version.returncode != 0 or first_line.strip().lower() != "tesseract 5.5.3":
            raise OCRUnavailableError("Tesseract 5.5.3 is required")
        if languages.returncode != 0 or self.language not in languages.stdout.splitlines():
            raise OCRUnavailableError(f"Tesseract language data '{self.language}' is unavailable")
        executable_path = Path(executable).resolve()
        configured_prefix = os.environ.get("TESSDATA_PREFIX")
        prefix_path = Path(configured_prefix) if configured_prefix else None
        candidates = [
            prefix_path / f"{self.language}.traineddata" if prefix_path else None,
            prefix_path / "tessdata" / f"{self.language}.traineddata" if prefix_path else None,
            executable_path.parent / "tessdata" / f"{self.language}.traineddata",
            executable_path.parent.parent / "share" / "tessdata" / f"{self.language}.traineddata",
        ]
        traineddata = next((candidate for candidate in candidates if candidate is not None and candidate.is_file()), None)
        if traineddata is None:
            raise OCRUnavailableError(f"Tesseract traineddata '{self.language}' could not be located")
        try:
            self._traineddata_digest = hashlib.sha256(traineddata.read_bytes()).hexdigest()
        except OSError as exc:
            raise OCRUnavailableError("Tesseract language data could not be read") from exc
        self._version = first_line.strip()
        self._resolved_executable = executable
        return self._resolved_executable

    def recognize(self, image_bytes: bytes) -> OCRResult:
        executable = self._verify()
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ExtractionError("OCR image exceeds the 20 megapixel limit")
                clean = image.convert("RGB")
                with tempfile.TemporaryDirectory(prefix="law-rag-ocr-") as temp_dir:
                    input_path = Path(temp_dir) / "page.png"
                    clean.save(input_path, format="PNG")
                    command = [executable, str(input_path), "stdout", "-l", self.language, "--psm", "6", "tsv"]
                    completed = subprocess.run(
                        command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=self.timeout_seconds, cwd=temp_dir,
                    )
        except ExtractionError:
            raise
        except subprocess.TimeoutExpired as exc:
            raise ExtractionError("Local OCR exceeded its time limit") from exc
        except (OSError, ValueError) as exc:
            raise ExtractionError("Local OCR could not process the image") from exc
        if completed.returncode != 0:
            LOGGER.warning("Tesseract failed exit_code=%d", completed.returncode)
            raise ExtractionError("Local OCR failed")
        words: list[OCRWord] = []
        try:
            for row in csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"):
                text = (row.get("text") or "").strip()
                confidence = float(row.get("conf", "-1"))
                if not text or confidence < 0:
                    continue
                left, top = float(row["left"]), float(row["top"])
                width, height = float(row["width"]), float(row["height"])
                words.append(OCRWord(text, confidence, (left, top, left + width, top + height)))
        except (KeyError, TypeError, ValueError) as exc:
            raise ExtractionError("Local OCR returned malformed confidence data") from exc
        mean = sum(word.confidence for word in words) / len(words) if words else 0.0
        return OCRResult(
            tuple(words), mean,
            (("tesseract", self._version or "unknown"), ("traineddata", f"{self.language}:sha256:{self._traineddata_digest}")),
        )
