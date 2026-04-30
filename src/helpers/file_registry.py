import os

from langchain_community.document_loaders import (
    BSHTMLLoader,
    CSVLoader,
    Docx2txtLoader,
    PyMuPDFLoader,
    TextLoader,
)
SUPPORTED_FILE_TYPES = {
    ".txt": {
        "mime_types": {"text/plain"},
        "loader": lambda path: TextLoader(file_path=path, encoding="utf-8"),
    },
    ".pdf": {
        "mime_types": {"application/pdf"},
        "loader": lambda path: PyMuPDFLoader(file_path=path),
    },
    ".docx": {
        "mime_types": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        "loader": lambda path: Docx2txtLoader(file_path=path),
    },
    ".csv": {
        "mime_types": {"text/csv"},
        "loader": lambda path: CSVLoader(file_path=path),
    },
    ".html": {
        "mime_types": {"text/html"},
        "loader": lambda path: BSHTMLLoader(file_path=path, open_encoding="utf-8"),
    },
    
}


def normalize_file_extension(file_name: str) -> str:
    return os.path.splitext(file_name)[-1].lower()


def is_supported_file(file_name: str) -> bool:
    return normalize_file_extension(file_name) in SUPPORTED_FILE_TYPES


def is_supported_content_type(file_name: str, content_type: str | None) -> bool:
    if not content_type:
        return True
    file_config = SUPPORTED_FILE_TYPES.get(normalize_file_extension(file_name))
    if file_config is None:
        return False
    return content_type in file_config["mime_types"]


def get_file_loader_factory(file_name: str):
    file_config = SUPPORTED_FILE_TYPES.get(normalize_file_extension(file_name))
    if file_config is None:
        return None
    return file_config["loader"]
