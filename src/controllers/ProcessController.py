from .BaseController import BaseController
from .ProjectController import ProjectController
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from models import processingEnum
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os 
class ProcessController(BaseController):
    def __init__(self,project_id:str):
        super().__init__()
        self.project_id=project_id
        self.project_path=ProjectController().get_project_files_path(project_id=project_id)

    def get_file_extension(self,file_id:str) :
        return os.path.splitext(file_id)[-1]
    
    def get_file_loader(self,file_id:str):
        file_path=os.path.join(
            self.project_path,file_id
        )
        file_ext=self.get_file_extension(file_id=file_id)
        if file_ext == processingEnum.TXT.value:
            return TextLoader(file_path= file_path,encoding="utf-8")
        if file_ext == processingEnum.PDF.value:
            return TextLoader(file_path= file_path,encoding="utf-8")
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

        
