from openai import OpenAI
import logging

from stores.LLMEnum import OpenAIEnums
from stores.LLMinterface import LLMInterface
class OpenAIprovider(LLMInterface):
    def __init__(self,api_key: str,api_url: str=None,
                 default_input_max_characters:int=1000,
                 default_generation_max_output_tokens:int=1000,
                 default_generation_temperature:float=0.1,):
        self.api_key=api_key
        self.api_url=api_url
        self.default_input_max_characters=default_input_max_characters
        self.default_generation_max_output_tokens=default_generation_max_output_tokens
        self.default_generation_temperature=default_generation_temperature
        self.genaration_model_id=None
        self.embedding_model_id=None
        self.embedding_size=None
        self.client=OpenAI(api_key=self.api_key,
                           api_url=self.api_url)
        self.logger = logging.getLogger(__name__)
        

    def set_genaration_model(self, model_id:str):
        self.genaration_model_id=model_id

    def set_embedding_model(self, model_id:str,embedding_size:int):
        self.embedding_model_id=model_id
        self.embedding_size=embedding_size

    def process_text(self,text:str):
        return text[:self.default_input_max_caracters].strip()


    def genarate_text(self, prompt:str,max_output_tokens:int=None,chat_history:list=[],temperature:float=None):
        if not self.client:
            self.logger.error("OpenAI CLIENT was not set ")
            return None
        if not self.generation_model_id:
            self.logger.error("generation model for OpenAI was not set ")
            return None
        max_output_tokens=max_output_tokens if max_output_tokens else self.default_output_max_caracters
        temperature=temperature if temperature  else self.default_temperature
        chat_history.append(self.constract_prompt(prompt=prompt,role=OpenAIEnums.USER.value))
        response=self.client.chat.completions.create(
            model=self.genaration_model_id,
            messages=chat_history,
            max_tokens=max_output_tokens,
            temperature=temperature
        )
        if not response or not response.choices or len(response.choices) == 0 or not response.choices[0].message:
            self.logger.error("Error while generating text with openai")
            return None
        return response.choices[0].message


        

    def embed_text(self, text:str,documant_type:str=None):
        if not self.client:
            self.logger.error("OpenAI CLIENT was not set ")
            return None
        if not self.embedding_model_id:
            self.logger.error("embedding model for OpenAI was not set ")
            return None
        response =self.client.embeddings.create(
            model=self.embedding_model_id,
            input=text
        )
        if response is None or response.data is None or len(response.data) == 0:
            self.logger.error("Error while embedding text with openai")
            return None
        return response.data[0].embedding
    def constract_prompt(self, prompt:str,role:str):
        return{
            "role":role,
            "content":self.process_text(text=prompt)
        }

