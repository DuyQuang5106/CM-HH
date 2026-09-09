import logging
import os
import json
import time
from typing import Dict, List, Tuple
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from cmhh.tracking.context import get_current_context
from cmhh.tracking.llm_call_logger import LLMCallRecord
from src.util.llm_client.base_llm_client import BaseLLMClient

_LOGGER = logging.getLogger("cmhh.llm")


class AzureGPTClient(BaseLLMClient):
    def __init__(
            self,
            config: dict,
            prompt_dir: str=None,
            output_dir: str=None,
        ):
        super().__init__(config, prompt_dir, output_dir)
        self.backend_name = "azure"

        self.api_version = config["api_version"]
        self.model = config["model"]
        self.azure_endpoint = config["azure_endpoint"]

        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
        self.client = AzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            azure_ad_token_provider=token_provider,
            api_version=self.api_version,
            max_retries=5,
        )


    def reset(self, output_dir:str=None) -> None:
        self.messages = []
        if output_dir is not None:
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

    def chat_once(self) -> str:
        call_id = self.current_call_id or "unknown"
        attempt = self.current_attempt
        ctx = get_current_context()
        call_logger = self._get_call_logger()

        start_time = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                seed=self.seed,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                stream=False,
            )
            latency_s = time.perf_counter() - start_time
            response_content = response.choices[-1].message.content

            input_tokens = getattr(getattr(response, "usage", None), "prompt_tokens", None)
            output_tokens = getattr(getattr(response, "usage", None), "completion_tokens", None)
            total_tokens = getattr(getattr(response, "usage", None), "total_tokens", None)
            token_str = ""
            if input_tokens is not None and output_tokens is not None:
                token_str = f" | tokens={input_tokens}+{output_tokens}={total_tokens or (input_tokens + output_tokens)}"

            _LOGGER.info("[LLM] %s <- SUCCESS | %.2fs%s", call_id, latency_s, token_str)

            if call_logger is not None:
                call_logger.log_attempt(LLMCallRecord(
                    call_id=call_id,
                    worker_id=ctx.worker_id,
                    attempt=attempt,
                    model=self.name,
                    backend=self.backend_name,
                    status_code=None,
                    reason="OK",
                    latency_s=latency_s,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    success=True,
                    task_id=ctx.task_id,
                    run_id=ctx.run_id,
                ))

            return response_content
        except Exception as exc:
            latency_s = time.perf_counter() - start_time
            status_code = getattr(exc, "status_code", None)
            if call_logger is not None:
                call_logger.log_attempt(LLMCallRecord(
                    call_id=call_id,
                    worker_id=ctx.worker_id,
                    attempt=attempt,
                    model=self.name,
                    backend=self.backend_name,
                    status_code=status_code,
                    latency_s=latency_s,
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    task_id=ctx.task_id,
                    run_id=ctx.run_id,
                ))
            raise

    def chat_once_with_tools(self, tools: List[Dict] = None) -> Tuple[str, List[Tuple[str, Dict]]]:
        call_id = self.current_call_id or "unknown"
        attempt = self.current_attempt
        ctx = get_current_context()
        call_logger = self._get_call_logger()

        start_time = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tools,
                tool_choice="auto",
                seed=self.seed,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                stream=False,
            )
            latency_s = time.perf_counter() - start_time
            function_name_parameters = []
            response_content = str(response.choices[-1].message.content)
            for tool_call in response.choices[-1].message.tool_calls:
                function_name = tool_call.function.name
                parameters = json.loads(tool_call.function.arguments)
                function_name_parameters.append((function_name, parameters))

            input_tokens = getattr(getattr(response, "usage", None), "prompt_tokens", None)
            output_tokens = getattr(getattr(response, "usage", None), "completion_tokens", None)
            total_tokens = getattr(getattr(response, "usage", None), "total_tokens", None)
            token_str = ""
            if input_tokens is not None and output_tokens is not None:
                token_str = f" | tokens={input_tokens}+{output_tokens}={total_tokens or (input_tokens + output_tokens)}"

            _LOGGER.info("[LLM] %s <- SUCCESS (tools) | %.2fs%s", call_id, latency_s, token_str)

            if call_logger is not None:
                call_logger.log_attempt(LLMCallRecord(
                    call_id=call_id,
                    worker_id=ctx.worker_id,
                    attempt=attempt,
                    model=self.name,
                    backend=self.backend_name,
                    status_code=None,
                    reason="OK",
                    latency_s=latency_s,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    success=True,
                    task_id=ctx.task_id,
                    run_id=ctx.run_id,
                ))

            return response_content, function_name_parameters
        except Exception as exc:
            latency_s = time.perf_counter() - start_time
            status_code = getattr(exc, "status_code", None)
            if call_logger is not None:
                call_logger.log_attempt(LLMCallRecord(
                    call_id=call_id,
                    worker_id=ctx.worker_id,
                    attempt=attempt,
                    model=self.name,
                    backend=self.backend_name,
                    status_code=status_code,
                    latency_s=latency_s,
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    task_id=ctx.task_id,
                    run_id=ctx.run_id,
                ))
            raise

