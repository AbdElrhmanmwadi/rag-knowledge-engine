import os

import fitz

from models.enums.processingEnums import processingEnum


class FileParser:
    def parse(self, file_path: str):
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == processingEnum.TXT.value:
            return self._parse_text_file(file_path=file_path)
        if file_extension == processingEnum.PDF.value:
            return self._parse_pdf_file(file_path=file_path)
        raise ValueError(f"Unsupported file type for translation: {file_extension}")

    def _parse_text_file(self, file_path: str):
        with open(file_path, "r", encoding="utf-8", errors="replace") as file_handle:
            content = file_handle.read()

        return {
            "file_type": processingEnum.TXT.value,
            "sections": [
                {
                    "index": 1,
                    "text": content
                }
            ]
        }

    def _parse_pdf_file(self, file_path: str):
        document = fitz.open(file_path)
        sections = []
        try:
            for page_index, page in enumerate(document):
                sections.append({
                    "index": page_index + 1,
                    "text": page.get_text("text"),
                    "width": float(page.rect.width),
                    "height": float(page.rect.height)
                })
        finally:
            document.close()

        return {
            "file_type": processingEnum.PDF.value,
            "sections": sections
        }
