from .BaseController import BaseController
from .ProjectController import ProjectController
from helpers.file_registry import (
    get_file_loader_factory,
    normalize_file_extension,
    is_markdown_file,
)
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
from langchain_core.documents import Document
import os
class ProcessController(BaseController):
    def __init__(self,project_id:str):
        super().__init__()
        self.project_id=project_id
        self.project_path=ProjectController().get_project_files_path(project_id=project_id)

    def get_file_extension(self,file_id:str) :
        return normalize_file_extension(file_id)
    
    def get_file_loader(self,file_id:str):
        file_path=os.path.join(
            self.project_path,file_id
        )
        if not os.path.exists(file_path):
            return None
        factory = get_file_loader_factory(file_id)
        if factory is None:
            return None
        return factory(file_path)

        # if file_ext == processingEnum.TXT.value:
        #     return TextLoader(file_path= file_path,encoding="utf-8")
        # if file_ext == processingEnum.PDF.value:
        #     return PyMuPDFLoader(file_path= file_path)
        return None
    def get_file_content(self,file_id:str):
        loader=self.get_file_loader(file_id=file_id)
        if loader is None:
            return None
        return loader.load()
    
    def process_file_content(self,file_contant:str,file_id:str,chunk_size:int=100,overlap_size:int=20):

        # Markdown Q&A files are split per section (one chunk per ### question)
        # instead of by fixed character count, which would shred answers mid-sentence.
        if is_markdown_file(file_id):
            return self.process_markdown_content(
                file_contant=file_contant,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap_size,length_function=len)
        file_contant_text=[
            rec.page_content

            for rec in file_contant
          ]
        file_contant_metadata=[
            rec.metadata

            for rec in file_contant
          ]
        chunks = text_splitter.create_documents(texts=file_contant_text,metadatas=file_contant_metadata)
        return chunks

    def process_markdown_content(self,file_contant,chunk_size:int=100,overlap_size:int=20,max_section_chars:int=None):
        """Split a markdown Q&A file into one chunk per ### section.

        Each chunk keeps its question heading in the text (so the question itself is
        embedded alongside its answer) and records the source section / question in
        metadata. Sections without a ### question (file intro, table of contents) are
        navigational and skipped.

        max_section_chars defaults to the configured embedding input limit
        (INPUT_DAFAULT_MAX_CHARACTERS): the embedding/answer pipeline truncates any
        text beyond it, so a longer answer is split into pieces (the question heading
        re-attached to each) instead of being silently cut off.
        """
        if max_section_chars is None:
            max_section_chars = getattr(
                getattr(self, "app_settings", None), "INPUT_DAFAULT_MAX_CHARACTERS", None
            ) or 1024

        full_text = "\n".join(rec.page_content for rec in file_contant)
        base_metadata = dict(file_contant[0].metadata) if file_contant else {}

        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("##", "section"), ("###", "question")],
        )
        sections = header_splitter.split_text(full_text)

        chunks = []
        for section in sections:
            question = section.metadata.get("question")
            if not question:
                continue
            metadata = {**base_metadata, **section.metadata}
            heading = f"### {question}\n\n"
            text = heading + section.page_content

            if len(text) <= max_section_chars:
                section.page_content = text
                section.metadata = metadata
                chunks.append(section)
                continue

            # Oversized answer: split the body and re-attach the heading to every
            # piece so each remains retrievable by its question.
            body_limit = max(max_section_chars - len(heading), 200)
            body_splitter = RecursiveCharacterTextSplitter(
                chunk_size=body_limit,
                chunk_overlap=min(max(overlap_size, 80), body_limit - 1),
                length_function=len,
            )
            for piece in body_splitter.split_text(section.page_content):
                chunks.append(Document(page_content=heading + piece, metadata=dict(metadata)))
        return chunks

        
