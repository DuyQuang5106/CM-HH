
import logging
import time
from typing import List, Dict, Tuple
import os
import json
from openai import OpenAI
from cmhh.tracking.context import get_current_context
from cmhh.tracking.llm_call_logger import LLMCallRecord
from src.util.llm_client.base_llm_client import BaseLLMClient

_LOGGER = logging.getLogger("cmhh.llm")

class VLLMClient(BaseLLMClient):
    def __init__(
            self,
            config: dict,
            prompt_dir: str=None,
            output_dir: str=None,
        ):
        super().__init__(config, prompt_dir, output_dir)
        self.backend_name = "vllm"

        self.base_url = config.get("base_url", "http://localhost:8000/v1")
        if "model" in config:
            self.model = config.get("model")
        elif "model_path" in config:
            self.model = config.get("model_path")
        else:
            raise Exception("No model or model_path in config")

        api_key = config.get("api_key", "EMPTY")
        self.client = OpenAI(base_url=self.base_url, api_key=api_key)

    def reset(self, output_dir: str=None) -> None:
        self.messages = []
        if output_dir is not None:
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

    def normalize_messages_for_vllm(self):
        norm = []
        for m in self.messages:
            c = m.get("content", "")
            if isinstance(c, list):
                text_parts = []
                for part in c:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                c = "\n".join(text_parts)
            elif not isinstance(c, str):
                c = str(c)
            norm.append({"role": m["role"], "content": c, **{k:v for k,v in m.items() if k not in ["role","content"]}})
        return norm

    def chat_once(self) -> str:
        messages = self.normalize_messages_for_vllm()
        call_id = self.current_call_id or "unknown"
        attempt = self.current_attempt
        ctx = get_current_context()
        call_logger = self._get_call_logger()

        start_time = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                seed=self.seed,
                stream=False,
            )
            latency_s = time.perf_counter() - start_time
            response_content = str(response.choices[-1].message.content or "") + str(response.choices[-1].message.reasoning_content or "")

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
        messages = self.normalize_messages_for_vllm()
        call_id = self.current_call_id or "unknown"
        attempt = self.current_attempt
        ctx = get_current_context()
        call_logger = self._get_call_logger()

        start_time = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="required",
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                seed=self.seed,
                stream=False,
            )
            latency_s = time.perf_counter() - start_time
            tool_calls = response.choices[-1].message.tool_calls or []
            response_content = str(response.choices[-1].message.content or "") + str(response.choices[-1].message.reasoning_content or "")
            function_name_parameters = []
            for tool_call in tool_calls:
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

