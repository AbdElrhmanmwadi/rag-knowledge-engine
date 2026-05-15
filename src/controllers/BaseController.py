from helpers.config import Settings,get_settings
import os
import random
import string
class BaseController:
    def __init__(self):
        self.app_settings: Settings = get_settings()
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        if self.app_settings.STORAGE_ROOT:
            storage_root = os.path.abspath(self.app_settings.STORAGE_ROOT)
            self.files_dir = os.path.join(storage_root, "files")
            self.database_dir = os.path.join(storage_root, "database")
        else:
            self.files_dir = os.path.join(self.base_dir, "assets", "files")
            self.database_dir = os.path.join(self.base_dir, "assets", "database")

    def generate_random_string(self,length:int=12):
        return ''.join(random.choices(string.ascii_lowercase + string.digits,k=length))
    def get_database_name(self,db_name:str):
        
        database_path=os.path.join(self.database_dir,db_name)
        if not os.path.exists(database_path):
            os.makedirs(database_path)
        
        return database_path   
   


    
