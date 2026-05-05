from .BaseController import BaseController
from .ProjectController import ProjectController
from helpers.file_registry import get_file_loader_factory, normalize_file_extension
from langchain_text_splitters import RecursiveCharacterTextSplitter
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

        
