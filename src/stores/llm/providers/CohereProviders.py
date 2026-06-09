
from abc import abstractmethod

import cohere

import logging

from stores.LLMEnum import CohereEnums
from stores.LLMinterface import LLMInterface
from helpers.observability import traceable
from typing import List,Union
class CoHereProvider(LLMInterface):
    def __init__(self,api_key: str,api_url: str=None,
                 default_input_max_characters:int=1000,
                 default_generation_max_output_tokens:int=1000,
                 default_generation_temperature:float=0.1,):
        
        self.api_key=api_key
        self.default_input_max_characters=default_input_max_characters
        self.default_generation_max_output_tokens=default_generation_max_output_tokens
        self.default_generation_temperature=default_generation_temperature
        self.genaration_model_id=None
        self.embedding_model_id=None
        self.embedding_size=None
        self.enums=CohereEnums
        self.client=cohere.Client(api_key=self.api_key)
        self.logger=logging.getLogger(__name__)

    def set_genaration_model(self, model_id:str):
        self.genaration_model_id=model_id

    def set_embedding_model(self, model_id:str,embedding_size:int):
         self.embedding_model_id=model_id
         self.embedding_size=embedding_size

    def process_text(self,text:str):
        return text[:self.default_input_max_characters].strip()
        
    @traceable(run_type="llm", name="cohere.generate_text")
    def genarate_text(self, prompt:str,max_output_tokens:int=None,chat_history:list=None,temperature:float=None):
        if not self.client:
               self.logger.error("Cohere CLIENT was not set ")
               return None
        if not self.genaration_model_id:
                self.logger.error("generation model for Cohere was not set ")
                return None
        max_output_tokens=max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        # `is not None` (not a truthy check): temperature=0 is a valid, deterministic
        # setting — a plain `if temperature` would wrongly fall back to the default.
        temperature=temperature if temperature is not None else self.default_generation_temperature
        chat_history = list(chat_history) if chat_history else []
        response= self.client.chat(
                model=self.genaration_model_id,
                chat_history=chat_history,
                message=prompt,
                temperature=temperature,
                max_tokens=max_output_tokens

            )
        if not response or not response.text:
                self.logger.error("Error while genaration text with Cohere")
                return None
        return response.text
    
    def embed_text(self, text:Union[str,List[str]],document_type:str=None):
        if not self.client:
                    self.logger.error("OpenAI CLIENT was not set ")
                    return None
        if not self.embedding_model_id:
                    self.logger.error("embedding model for OpenAI was not set ")
                    return None
        input_type=CohereEnums.DOCUMENT.value 
        if document_type == CohereEnums.QUERY.value:
                input_type=CohereEnums.QUERY.value
        response =self.client.embed(
                model=self.embedding_model_id,
                texts=[self.process_text(text)] if isinstance(text, str) else [self.process_text(t) for t in text],
                input_type=input_type,
                embedding_types=['float'],
            )
        if not response or not response.embeddings or not response.embeddings.float:
                 self.logger.error("Error while embedding text with CoHere")
                 return None
        
        return [i for i in response.embeddings.float]
  
    def constract_prompt(self, prompt:str,role:str):
         return{
            "role":role,
            "text":self.process_text(text=prompt)
        }
