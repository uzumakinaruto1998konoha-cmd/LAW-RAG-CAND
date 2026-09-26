"""Streaming upload bounds and content-based format validation."""

from __future__ import annotations

import io
import hashlib
import logging
import struct
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from .errors import UnsupportedFileError, UploadTooLargeError, UploadValidationError

LOGGER = logging.getLogger(__name__)
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_DOCX_ENTRIES = 10_000
READ_BLOCK_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    original_filename: str
    extension: str
    media_type: str
    size_bytes: int
    sha256: str
    content: bytes


def _image_dimensions(data: bytes, extension: str) -> tuple[int, int] | None:
    if extension == ".png":
        if len(data) < 24 or data[12:16] != b"IHDR":
            return None
        return struct.unpack(">II", data[16:24])
    if extension == ".jpg":
        offset = 2
        while offset + 4 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(data):
                return None
            segment_length = int.from_bytes(data[offset:offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(data):
                return None
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if segment_length < 7:
                    return None
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return width, height
            offset += segment_length
    return None


def _validate_docx(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES or sum(item.file_size for item in entries) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise UploadValidationError("DOCX package exceeds safe expansion limits")
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UploadValidationError("DOCX package is missing required document parts")
            bad_member = archive.testzip()
            if bad_member is not None:
                raise UploadValidationError("DOCX package integrity check failed")
    except zipfile.BadZipFile as exc:
        raise UploadValidationError("DOCX package is not a valid ZIP container") from exc


def validate_upload(
    filename: str,
    stream: io.BufferedIOBase,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> ValidatedUpload:
    """Read within the configured bound and validate extension against content.

    No user-controlled filename is used as a filesystem path. The complete
    bounded content is returned for atomic quarantine storage by the caller.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if not filename or "\x00" in filename or len(filename) > 255:
        raise UploadValidationError("Filename is empty or invalid")
    extension = PurePath(filename.replace("\\", "/")).suffix.lower()
    chunks: list[bytes] = []
    size = 0
    digest = hashlib.sha256()
    while True:
        try:
            block = stream.read(min(READ_BLOCK_BYTES, max_bytes + 1 - size))
        except (OSError, ValueError) as exc:
            LOGGER.warning("Upload stream read failed")
            raise UploadValidationError("Uploaded content could not be read") from exc
        if not block:
            break
        size += len(block)
        if size > max_bytes:
            raise UploadTooLargeError(f"Upload exceeds maximum size of {max_bytes} bytes")
        digest.update(block)
        chunks.append(block)
    content = b"".join(chunks)
    if not content:
        raise UploadValidationError("Empty files are not accepted")

    signatures = {
        ".pdf": (
            content.startswith(b"%PDF-")
            and b"%%EOF" in content[-2048:]
            and b"startxref" in content[-4096:]
            and b" obj" in content,
            "application/pdf",
        ),
        ".jpg": (content.startswith(b"\xff\xd8\xff"), "image/jpeg"),
        ".jpeg": (content.startswith(b"\xff\xd8\xff"), "image/jpeg"),
        ".png": (content.startswith(b"\x89PNG\r\n\x1a\n"), "image/png"),
    }
    if extension == ".docx":
        _validate_docx(content)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif extension == ".txt":
        try:
            content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise UploadValidationError("Text file must be valid UTF-8") from exc
        media_type = "text/plain; charset=utf-8"
    elif extension in signatures:
        matches, media_type = signatures[extension]
        if not matches:
            raise UnsupportedFileError("File extension does not match its content signature")
    else:
        raise UnsupportedFileError("File format is not supported")

    if extension in (".png", ".jpg", ".jpeg"):
        dimensions = _image_dimensions(content, ".jpg" if extension == ".jpeg" else extension)
        if dimensions is None or dimensions[0] <= 0 or dimensions[1] <= 0:
            raise UploadValidationError("Image dimensions could not be validated")
        if dimensions[0] * dimensions[1] > MAX_IMAGE_PIXELS:
            raise UploadValidationError("Image exceeds the 20 megapixel limit")
    LOGGER.info("Validated upload extension=%s size_bytes=%d sha256=%s", extension, size, digest.hexdigest())
    return ValidatedUpload(filename, extension, media_type, size, digest.hexdigest(), content)
