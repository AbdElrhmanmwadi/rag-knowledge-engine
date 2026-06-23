
from abc import abstractmethod

import cohere

import logging

from stores.LLMEnum import CohereEnums
from stores.LLMinterface import LLMInterface
from helpers.observability import traceable, add_llm_run_metadata, reduce_stream_chunks
from helpers.streaming import open_stream_with_retry
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
        self.rerank_model_id=None
        self.enums=CohereEnums
        self.client=cohere.Client(api_key=self.api_key)
        self.logger=logging.getLogger(__name__)

    def set_genaration_model(self, model_id:str):
        self.genaration_model_id=model_id

    def set_rerank_model(self, model_id:str):
        self.rerank_model_id=model_id

    def rerank_documents(self, query:str, documents:List[str], top_n:int):
        """Re-score (query, document) pairs with Cohere's cross-encoder reranker.

        Returns the reranker results ordered by relevance, each carrying the
        original `index` into `documents` and a `relevance_score`. Returns None
        on any failure so callers can fall back to the vector-search order.
        """
        if not self.client:
            self.logger.error("Cohere CLIENT was not set")
            return None
        model_id = self.rerank_model_id
        if not model_id:
            self.logger.error("rerank model for Cohere was not set")
            return None
        if not documents:
            return []
        try:
            response = self.client.rerank(
                model=model_id,
                query=query,
                documents=documents,
                top_n=min(top_n, len(documents)),
            )
        except Exception as e:
            self.logger.error(f"Error while reranking with Cohere: {e}")
            return None
        return getattr(response, "results", None)

    def set_embedding_model(self, model_id:str,embedding_size:int):
         self.embedding_model_id=model_id
         self.embedding_size=embedding_size

    def process_text(self,text:str):
        return text[:self.default_input_max_characters].strip()
        
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
        result = self._chat(
            prompt=prompt,
            chat_history=chat_history,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return result["text"] if result else None

    # LangSmith only counts tokens when the traced llm run's outputs carry a
    # `usage_metadata` key, so the traced call returns a dict and genarate_text
    # unwraps the text for callers.
    @traceable(run_type="llm", name="cohere.generate_text", metadata={"ls_provider": "cohere"})
    def _chat(self, prompt:str, chat_history:list, temperature:float, max_output_tokens:int):
        add_llm_run_metadata(model=self.genaration_model_id, provider="cohere")
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
        output = {"text": response.text}
        usage = self._usage_metadata(response)
        if usage:
            output["usage_metadata"] = usage
        return output

    def genarate_text_stream(self, prompt:str,max_output_tokens:int=None,chat_history:list=None,temperature:float=None):
        if not self.client:
            self.logger.error("Cohere CLIENT was not set ")
            return
        if not self.genaration_model_id:
            self.logger.error("generation model for Cohere was not set ")
            return
        max_output_tokens=max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        # `is not None` (not a truthy check): temperature=0 is a valid, deterministic
        # setting — a plain `if temperature` would wrongly fall back to the default.
        temperature=temperature if temperature is not None else self.default_generation_temperature
        chat_history = list(chat_history) if chat_history else []
        for item in self._chat_stream(
            prompt=prompt,
            chat_history=chat_history,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ):
            # The traced generator also yields a final usage_metadata item for
            # LangSmith; only the text chunks go to the caller.
            text = item.get("text") if isinstance(item, dict) else None
            if text:
                yield text

    @traceable(
        run_type="llm",
        name="cohere.generate_text_stream",
        metadata={"ls_provider": "cohere"},
        reduce_fn=reduce_stream_chunks,
    )
    def _chat_stream(self, prompt:str, chat_history:list, temperature:float, max_output_tokens:int):
        add_llm_run_metadata(model=self.genaration_model_id, provider="cohere")
        stream = open_stream_with_retry(
            lambda: self.client.chat_stream(
                model=self.genaration_model_id,
                chat_history=chat_history,
                message=prompt,
                temperature=temperature,
                max_tokens=max_output_tokens,
            ),
            logger=self.logger,
        )
        for event in stream:
            event_type = getattr(event, "event_type", None)
            if event_type == "text-generation" and getattr(event, "text", None):
                yield {"text": event.text}
            elif event_type == "stream-end":
                usage = self._usage_metadata(getattr(event, "response", None))
                if usage:
                    yield {"usage_metadata": usage}

    @staticmethod
    def _usage_metadata(response):
        meta = getattr(response, "meta", None)
        tokens = getattr(meta, "billed_units", None) or getattr(meta, "tokens", None)
        input_tokens = getattr(tokens, "input_tokens", None)
        output_tokens = getattr(tokens, "output_tokens", None)
        if input_tokens is None and output_tokens is None:
            return None
        return {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "total_tokens": int(input_tokens or 0) + int(output_tokens or 0),
        }
    
    def rerank_documents(self, query:str, documents:List[str], model:str, top_n:int=None):
        """Reorder documents by relevance to query using Cohere Rerank.

        Returns a list of original indices in ranked order (best first), trimmed
        to top_n. Returns None if the call cannot be made, so the caller can fall
        back to the vector-search order instead of dropping results.
        """
        if not self.client:
            self.logger.error("Cohere CLIENT was not set ")
            return None
        if not documents:
            return []
        response = self._rerank(
            query=query,
            documents=documents,
            model=model,
            top_n=top_n if top_n else len(documents),
        )
        if response is None:
            return None
        return [result.index for result in response.results]

    @traceable(run_type="chain", name="cohere.rerank", metadata={"ls_provider": "cohere"})
    def _rerank(self, query:str, documents:List[str], model:str, top_n:int):
        add_llm_run_metadata(model=model, provider="cohere")
        return self.client.rerank(
            model=model,
            query=query,
            documents=documents,
            top_n=top_n,
        )

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
