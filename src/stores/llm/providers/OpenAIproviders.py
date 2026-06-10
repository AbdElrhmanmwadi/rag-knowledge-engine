from openai import OpenAI
import logging

from stores.LLMEnum import OpenAIEnums
from stores.LLMinterface import LLMInterface
from helpers.observability import traceable, add_llm_run_metadata
from typing import List,Union
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
        self.enums=OpenAIEnums
        self.client=OpenAI(api_key=self.api_key,
                           base_url=self.api_url)
        self.logger = logging.getLogger(__name__)
        

    def set_genaration_model(self, model_id:str):
        self.genaration_model_id=model_id

    def set_embedding_model(self, model_id:str,embedding_size:int):
        self.embedding_model_id=model_id
        self.embedding_size=embedding_size

    def process_text(self,text:str):
        return text[:self.default_input_max_characters].strip()


    def genarate_text(self, prompt:str,max_output_tokens:int=None,chat_history:list=None,temperature:float=None):
        if not self.client:
            self.logger.error("OpenAI CLIENT was not set ")
            return None
        if not self.genaration_model_id:
            self.logger.error("generation model for OpenAI was not set ")
            return None
        max_output_tokens=max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        # `is not None` (not a truthy check): temperature=0 is a valid, deterministic
        # setting — a plain `if temperature` would wrongly fall back to the default.
        temperature=temperature if temperature is not None else self.default_generation_temperature
        # Do NOT truncate the generation prompt with process_text (that limit is for
        # embedding inputs); truncating here would cut the question off the RAG prompt.
        # Copy so we never mutate the caller's list (and avoid a shared mutable default).
        chat_history = list(chat_history) if chat_history else []
        chat_history.append({"role": OpenAIEnums.USER.value, "content": prompt})
        result = self._chat(
            chat_history=chat_history,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        # Return the text, not the message object (the object is not JSON-serializable
        # and downstream callers serialize this value directly into the API response).
        return result["text"] if result else None

    # LangSmith only counts tokens when the traced llm run's outputs carry a
    # `usage_metadata` key, so the traced call returns a dict and genarate_text
    # unwraps the text for callers.
    @traceable(run_type="llm", name="openai.generate_text", metadata={"ls_provider": "openai"})
    def _chat(self, chat_history:list, temperature:float, max_output_tokens:int):
        add_llm_run_metadata(model=self.genaration_model_id, provider="openai")
        response=self.client.chat.completions.create(
            model=self.genaration_model_id,
            messages=chat_history,
            max_tokens=max_output_tokens,
            temperature=temperature
        )
        if not response or not response.choices or len(response.choices) == 0 or not response.choices[0].message:
            self.logger.error("Error while generating text with openai")
            return None
        output = {"text": response.choices[0].message.content}
        usage = getattr(response, "usage", None)
        if usage is not None:
            output["usage_metadata"] = {
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            }
        return output


        

    def embed_text(self, text:Union[str,List[str]],document_type:str=None):
        if not self.client:
            self.logger.error("OpenAI CLIENT was not set ")
            return None
        if not self.embedding_model_id:
            self.logger.error("embedding model for OpenAI was not set ")
            return None
        response =self.client.embeddings.create(
            model=self.embedding_model_id,
            input=[text] if isinstance(text, str) else [self.process_text(t) for t in text]
        )
        if response is None or response.data is None or len(response.data) == 0:
            self.logger.error("Error while embedding text with openai")
            return None
        return [item.embedding for item in response.data]
    def constract_prompt(self, prompt:str,role:str):
        return{
            "role":role,
            "content":self.process_text(text=prompt)
        }

