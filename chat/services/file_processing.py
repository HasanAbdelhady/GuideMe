# chat/services/file_processing.py
import logging
import os
import re
from typing import Any, Dict, Optional

from django.core.files.storage import default_storage

from pdfminer.high_level import extract_text

from .interfaces import FileProcessingServiceInterface


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters"""
    return re.sub(r'[<>:"/\\\\|?*]', "_", filename)


class FileProcessingService(FileProcessingServiceInterface):
    """Service for handling file processing operations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def extract_text_from_uploaded_file(
        self, uploaded_file, max_chars: int = 15000
    ) -> Dict[str, Any]:
        """Extract text content from uploaded files (PDF, TXT)"""
        filename = uploaded_file.name
        text_content = ""
        was_truncated = False
        original_char_count = 0

        file_extension = os.path.splitext(filename)[1].lower()

        try:
            extracted_text_for_counting = ""
            if file_extension == ".pdf":
                uploaded_file.seek(0)
                raw_text = extract_text(uploaded_file.file)
                extracted_text_for_counting = raw_text.strip() if raw_text else ""
            elif file_extension == ".txt":
                uploaded_file.seek(0)
                raw_bytes = uploaded_file.read()
                extracted_text_for_counting = raw_bytes.decode(
                    "utf-8", errors="replace"
                ).strip()
            else:
                extracted_text_for_counting = f"[Unsupported file type: {file_extension}. Only .pdf and .txt are currently supported for direct text extraction.]"

            original_char_count = len(extracted_text_for_counting)

            if original_char_count > max_chars:
                text_content = extracted_text_for_counting[:max_chars]
                was_truncated = True
            else:
                text_content = extracted_text_for_counting

        except Exception as e:
            self.logger.error(
                f"Error extracting text from {filename}: {e}", exc_info=True
            )
            text_content = f"[Error extracting text from file: {filename}. Please try again or ensure the file is valid.]"
            original_char_count = 0
            was_truncated = False

        return {
            "filename": filename,
            "text_content": text_content,
            "was_truncated": was_truncated,
            "original_char_count": original_char_count,
            "final_char_count": len(text_content),
        }

    def save_file(self, chat_id: str, uploaded_file) -> Optional[str]:
        """Save uploaded file and return the file path"""
        if uploaded_file:
            return default_storage.save(
                f"media/chat_uploads/{chat_id}/{uploaded_file.name}", uploaded_file
            )
        return None
