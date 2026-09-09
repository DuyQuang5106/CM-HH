import logging
import os
import ast
import time
from cmhh.tracking.context import get_current_context
from cmhh.tracking.llm_call_logger import LLMCallRecord
from src.util.llm_client.base_llm_client import BaseLLMClient

_LOGGER = logging.getLogger("cmhh.llm")


class LocalModelClient(BaseLLMClient):
    def __init__(
            self,
            config: dict,
            prompt_dir: str=None,
            output_dir: str=None,
        ):
        super().__init__(config, prompt_dir, output_dir)
        self.backend_name = "local"

        try:
            import transformers
            import torch
        except ImportError:
            transformers = None
            torch = None

        if os.getenv("AMLT_DATA_DIR"):
            self.model = os.path.join(os.getenv("AMLT_DATA_DIR"), os.path.normpath(config['model_path']))
        else:
            self.model = os.path.normpath(config['model_path'])

        if transformers is not None and torch is not None:
            self.pipeline = transformers.pipeline(
                "text-generation",
                model=self.model,
                model_kwargs={"torch_dtype": torch.bfloat16}
            )
        else:
            self.pipeline = None

    def chat_once(self) -> str:
        call_id = self.current_call_id or "unknown"
        attempt = self.current_attempt
        ctx = get_current_context()
        call_logger = self._get_call_logger()

        format_messages = []
        for m in self.messages:
            c = m.get("content", "")
            if isinstance(c, list):
                parts = []
                for p in c:
                    if isinstance(p, dict) and p.get("type") == "text":
                        parts.append(p.get("text", ""))
                    elif isinstance(p, str):
                        parts.append(p)
                c = "\n".join(parts)
            elif not isinstance(c, str):
                c = str(c)
            format_messages.append({"role": m["role"], "content": c})

        text = self.pipeline.tokenizer.apply_chat_template(
            format_messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=self.think,
        )
        start_time = time.perf_counter()
        try:
            response = self.pipeline(
                text,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                do_sample=True,
                return_full_text=False,
            )
            latency_s = time.perf_counter() - start_time
            response_content = response[0]["generated_text"].strip()
            _LOGGER.info("[LLM] %s <- SUCCESS | backend=local | %.2fs", call_id, latency_s)

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
                    success=True,
                    task_id=ctx.task_id,
                    run_id=ctx.run_id,
                ))

            return response_content
        except Exception as exc:
            latency_s = time.perf_counter() - start_time
            if call_logger is not None:
                call_logger.log_attempt(LLMCallRecord(
                    call_id=call_id,
                    worker_id=ctx.worker_id,
                    attempt=attempt,
                    model=self.name,
                    backend=self.backend_name,
                    latency_s=latency_s,
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    task_id=ctx.task_id,
                    run_id=ctx.run_id,
                ))
            raise

