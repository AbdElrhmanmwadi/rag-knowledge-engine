import os
import textwrap

import fitz

from models.enums.processingEnums import processingEnum


class FileRebuilder:
    def rebuild(self, parsed_file: dict, translated_sections: list, output_file_path: str):
        file_type = parsed_file.get("file_type")
        if file_type == processingEnum.TXT.value:
            self._rebuild_text_file(translated_sections=translated_sections, output_file_path=output_file_path)
            return output_file_path
        if file_type == processingEnum.PDF.value:
            self._rebuild_pdf_file(parsed_file=parsed_file, translated_sections=translated_sections, output_file_path=output_file_path)
            return output_file_path
        raise ValueError(f"Unsupported file type for rebuild: {file_type}")

    def _rebuild_text_file(self, translated_sections: list, output_file_path: str):
        translated_text = "\n\n".join(section.get("translated_text", "") for section in translated_sections)
        with open(output_file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(translated_text)

    def _rebuild_pdf_file(self, parsed_file: dict, translated_sections: list, output_file_path: str):
        output_document = fitz.open()
        try:
            section_lookup = {
                section.get("index"): section
                for section in parsed_file.get("sections", [])
            }
            for translated_section in translated_sections:
                source_section = section_lookup.get(translated_section.get("index"), {})
                page_width = source_section.get("width", 595.0)
                page_height = source_section.get("height", 842.0)
                self._append_pdf_pages(
                    output_document=output_document,
                    text=translated_section.get("translated_text", ""),
                    page_width=page_width,
                    page_height=page_height
                )
            output_document.save(output_file_path)
        finally:
            output_document.close()

    def _append_pdf_pages(self, output_document, text: str, page_width: float, page_height: float):
        font_size = 11
        line_height = 16
        margin_x = 40
        margin_y = 50
        usable_width = max(page_width - (margin_x * 2), 100)
        usable_height = max(page_height - (margin_y * 2), 100)
        chars_per_line = max(20, int(usable_width / 6))
        lines_per_page = max(10, int(usable_height / line_height))

        wrapped_lines = []
        for paragraph in (text or "").splitlines():
            if not paragraph.strip():
                wrapped_lines.append("")
                continue
            wrapped_lines.extend(textwrap.wrap(paragraph, width=chars_per_line) or [""])

        if not wrapped_lines:
            wrapped_lines = [""]

        current_index = 0
        while current_index < len(wrapped_lines):
            page = output_document.new_page(width=page_width, height=page_height)
            y_position = margin_y
            for _ in range(lines_per_page):
                if current_index >= len(wrapped_lines):
                    break
                page.insert_text(
                    fitz.Point(margin_x, y_position),
                    wrapped_lines[current_index],
                    fontsize=font_size
                )
                current_index += 1
                y_position += line_height
