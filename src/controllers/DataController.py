import os

from .BaseController import BaseController
from .ProjectController import ProjectController
from fastapi import UploadFile, File
from models import ResponseStatus
import re
class DataController(BaseController):
    def __init__(self):
        super().__init__()
    async def validate_uploaded_file(self, file: UploadFile):
        # Implement your validation logic here
        # For example, check the file type, size, etc.
        if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
            return False, ResponseStatus.FILE_TYPE_NOT_SUPPORTED.value
            
        if file.size > self.app_settings.FILE_MAX_SIZE*1024*1024:
            return False, ResponseStatus.FILE_SIZE_EXCEEDED.value

        return True, ResponseStatus.FILE_VALIDATED_SUCCESS.value
    

    
        
    def generate_unique_filename(self, orig_file_name: str, project_id: str):

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

        return new_file_path

    def get_clean_file_name(self, orig_file_name: str):

        # remove any special characters, except underscore and .
        cleaned_file_name = re.sub(r'[^\w.]', '', orig_file_name.strip())

        # replace spaces with underscore
        cleaned_file_name = cleaned_file_name.replace(" ", "_")

        return cleaned_file_name
