"""Content bounds enforcement and decompression bomb defense.

Limits response payloads to 5 MB and guards against gzip/deflate zip bombs
using streaming decompression expansion ratio tracking.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model).
"""

from __future__ import annotations

import io
from typing import BinaryIO
import zlib

from ai_incident_monitor.security.exceptions import (
    DecompressionBombError,
    PayloadTooLargeError,
)

DEFAULT_MAX_BYTES: int = 5 * 1024 * 1024  # 5.0 MB (5,242,880 bytes)
DEFAULT_MAX_DECOMPRESSION_RATIO: float = 5.0
DEFAULT_CHUNK_SIZE: int = 64 * 1024  # 64 KB
RATIO_EVALUATION_THRESHOLD_BYTES: int = 100 * 1024  # 100 KB compressed before ratio check


class ContentLimits:
    """Enforces streaming payload size ceilings and decompression ratio safety."""

    def __init__(
        self,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_decompression_ratio: float = DEFAULT_MAX_DECOMPRESSION_RATIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self.max_bytes = max_bytes
        self.max_decompression_ratio = max_decompression_ratio
        self.chunk_size = chunk_size

    def check_content_length_header(self, content_length_header: str | None) -> None:
        """Pre-flight check against Content-Length header if present.

        Raises:
            PayloadTooLargeError: If Content-Length exceeds max_bytes.
        """
        if content_length_header is not None:
            try:
                length = int(content_length_header.strip())
                if length > self.max_bytes:
                    raise PayloadTooLargeError(
                        f"Content-Length {length} bytes exceeds maximum allowed limit of {self.max_bytes} bytes (5 MB)"
                    )
            except ValueError:
                # If Content-Length header is malformed, ignore and rely on streaming enforcement
                pass

    def read_stream(
        self,
        stream: BinaryIO,
        *,
        content_encoding: str | None = None,
    ) -> bytes:
        """Read a response stream chunk-by-chunk up to max_bytes with decompression protection.

        Args:
            stream: Readable binary stream (e.g. response.read or response.raw)
            content_encoding: Value of 'Content-Encoding' header (e.g. 'gzip', 'deflate')

        Returns:
            Fully read and safely decompressed bytes.

        Raises:
            PayloadTooLargeError: If payload exceeds max_bytes.
            DecompressionBombError: If decompression expansion ratio or ceiling is violated.
        """
        encoding = (content_encoding or "").lower().strip()
        is_compressed = encoding in ("gzip", "x-gzip", "deflate")

        if is_compressed:
            return self._read_compressed_stream(stream, encoding)
        return self._read_raw_stream(stream)

    def _read_raw_stream(self, stream: BinaryIO) -> bytes:
        """Read uncompressed stream strictly enforcing max_bytes limit."""
        buffer = bytearray()
        total_read = 0

        while True:
            chunk = stream.read(self.chunk_size)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > self.max_bytes:
                raise PayloadTooLargeError(
                    f"Payload stream exceeded maximum allowed size of {self.max_bytes} bytes"
                )
            buffer.extend(chunk)

        return bytes(buffer)

    def _read_compressed_stream(self, stream: BinaryIO, encoding: str) -> bytes:
        """Read and decompress stream in chunks, monitoring compression ratio."""
        # zlib.MAX_WBITS | 32 auto-detects zlib vs gzip header
        wbits = 16 + zlib.MAX_WBITS if "gzip" in encoding else zlib.MAX_WBITS | 32
        decompressor = zlib.decompressobj(wbits)

        buffer = bytearray()
        compressed_bytes = 0
        uncompressed_bytes = 0

        while True:
            chunk = stream.read(self.chunk_size)
            if not chunk:
                break

            compressed_bytes += len(chunk)
            if compressed_bytes > self.max_bytes:
                raise PayloadTooLargeError(
                    f"Compressed payload exceeded maximum allowed size of {self.max_bytes} bytes"
                )

            try:
                decompressed_chunk = decompressor.decompress(chunk)
            except zlib.error as exc:
                raise DecompressionBombError(f"Corrupt or invalid compressed payload: {exc}") from exc

            uncompressed_bytes += len(decompressed_chunk)
            if uncompressed_bytes > self.max_bytes:
                raise DecompressionBombError(
                    f"Decompressed payload size {uncompressed_bytes} bytes exceeded maximum limit of {self.max_bytes} bytes"
                )

            # Check expansion ratio after threshold
            if compressed_bytes >= RATIO_EVALUATION_THRESHOLD_BYTES:
                ratio = uncompressed_bytes / compressed_bytes
                if ratio > self.max_decompression_ratio:
                    raise DecompressionBombError(
                        f"Decompression expansion ratio {ratio:.2f}:1 exceeds maximum safe limit of {self.max_decompression_ratio}:1"
                    )

            buffer.extend(decompressed_chunk)

        # Flush remaining decompressor buffer
        try:
            remaining = decompressor.flush()
            uncompressed_bytes += len(remaining)
            if uncompressed_bytes > self.max_bytes:
                raise DecompressionBombError(
                    f"Decompressed payload size {uncompressed_bytes} bytes exceeded maximum limit of {self.max_bytes} bytes"
                )
            buffer.extend(remaining)
        except zlib.error as exc:
            raise DecompressionBombError(f"Decompression flush failed: {exc}") from exc

        return bytes(buffer)
