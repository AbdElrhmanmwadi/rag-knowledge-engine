from abc import ABC, abstractmethod

class LLMInterface(ABC):
    def set_generation_model(self, model_id: str):
        return self.set_genaration_model(model_id=model_id)

    @abstractmethod
    def set_genaration_model(self, model_id:str):
        pass

    @abstractmethod
    def set_embedding_model(self, model_id:str):
        pass
    @abstractmethod
    def genarate_text(self, prompt:str,max_output_tokens:int,chat_history:list=[], temperature:float=None):
        pass
    @abstractmethod
    def genarate_text_stream(self, prompt:str,max_output_tokens:int=None,chat_history:list=None, temperature:float=None):
        """Yield answer text chunks (str). Same arguments as genarate_text."""
        pass
    @abstractmethod
    def embed_text(self, text:str,documant_type:str=None):
        pass
    @abstractmethod
    def constract_prompt(self, prompt:str,role:str):
        pass

