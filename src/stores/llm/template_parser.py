import os
import logging
logger = logging.getLogger(__name__)
class TemplateParser:
    def __init__(self, language: str,defult_language: str="en"):
        self.curentPath = os.path.dirname(os.path.abspath(__file__))
        self.template_path = os.path.join(self.curentPath, "templete", "local")
        self.language = None
        self.defult_language = defult_language
        self.set_language(language=language)
    def set_language(self, language: str):
        if language is None:
            self.language = self.defult_language
            return
        language_path = os.path.join(self.template_path, language)
        if os.path.exists(language_path):
            self.language = language
        else:
            self.language = self.defult_language
    def get(self, group:str,key:str,vars:dict|None=None):
        if not group or not key:
            logger.error("no group or key")
            return None
        if vars is None:
            vars = {}
        group_path=os.path.join(self.template_path, self.language, f"{group}.py")
        targeted_language=self.language
        if not os.path.exists(group_path):
            logger.error(f"not os.path.exist{group_path}")
            group_path=os.path.join(self.template_path, self.defult_language, f"{group}.py")
            targeted_language=self.defult_language
        if not os.path.exists(group_path):
            logger.error(f"not os.path.exist{group_path}  *2*")

            
            return None
        try:
            module = __import__(f"stores.llm.templete.local.{targeted_language}.{group}", fromlist=["group"])
            if not module:
                logger.error("no module")
                return None
            key_attribute = getattr(module, key, None)
            if key_attribute is None:
                logger.error("no key_attribute")

                return None
            return key_attribute.substitute(vars)
        except (AttributeError, TypeError, ImportError) as e:
            return None
    
        

    


    
