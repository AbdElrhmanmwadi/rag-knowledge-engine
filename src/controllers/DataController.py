import os

from .BaseController import BaseController
from .ProjectController import ProjectController
from fastapi import UploadFile
from helpers.file_registry import is_supported_content_type, is_supported_file
from models import ResponseStatus
import re
class DataController(BaseController):
    def __init__(self):
        super().__init__()
    async def validate_uploaded_file(self, file: UploadFile):
        file_name = file.filename or ""

        if not is_supported_file(file_name):
            return False, ResponseStatus.FILE_TYPE_NOT_SUPPORTED.value

        if not is_supported_content_type(file_name, file.content_type):
            return False, ResponseStatus.FILE_TYPE_NOT_SUPPORTED.value

        file_size = file.size or 0
        if file_size > self.app_settings.FILE_MAX_SIZE*1024*1024:
            return False, ResponseStatus.FILE_SIZE_EXCEEDED.value

        return True, ResponseStatus.FILE_VALIDATED_SUCCESS.value
    

    
        
    def generate_unique_file_Path(self, orig_file_name: str, project_id: str):

        random_key = self.generate_random_string()
        project_path = ProjectController().get_project_files_path(project_id=project_id)

        cleaned_file_name = self.get_clean_file_name(
            orig_file_name=orig_file_name
        )

        new_file_path = os.path.join(
            project_path,
            random_key + "_" + cleaned_file_name
        )

        while os.path.exists(new_file_path):
            random_key = self.generate_random_string()
            new_file_path = os.path.join(
                project_path,
                random_key + "_" + cleaned_file_name
            )

        return new_file_path,random_key + "_" + cleaned_file_name

    def get_clean_file_name(self, orig_file_name: str):

        # remove any special characters, except underscore and .
        cleaned_file_name = re.sub(r'[^\w.]', '', orig_file_name.strip())

        # replace spaces with underscore
        cleaned_file_name = cleaned_file_name.replace(" ", "_")

        return cleaned_file_name
