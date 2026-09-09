import logging
import os
import json
import time
import requests
from cmhh.tracking.context import get_current_context
from cmhh.tracking.llm_call_logger import LLMCallRecord
from src.util.llm_client.base_llm_client import BaseLLMClient

_LOGGER = logging.getLogger("cmhh.llm")


class APIModelClient(BaseLLMClient):
    def __init__(
            self,
            config: dict,
            prompt_dir: str=None,
            output_dir: str=None,
        ):
        super().__init__(config, prompt_dir, output_dir)
        self.backend_name = "api"

        self.url = config["url"]
        model = config["model"]
        stream = config.get("stream", False)
        raw_key = config.get("api_key", "")
        if isinstance(raw_key, str) and "," in raw_key:
            self.api_keys = [k.strip() for k in raw_key.split(",") if k.strip()]
        elif isinstance(raw_key, list):
            self.api_keys = [str(k).strip() for k in raw_key if str(k).strip()]
        else:
            self.api_keys = [str(raw_key).strip()] if raw_key else []
        self._key_index = 0

        self.timeout = config.get("timeout", 120)
        self.payload = {
            "model": model,
            "stream": stream,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed
        }

    def reset(self, output_dir:str=None) -> None:
        self.messages = []
        if output_dir is not None:
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

    def chat_once(self) -> str:
        self.payload["messages"] = self.messages
        call_id = self.current_call_id or "unknown"
        attempt = self.current_attempt
        ctx = get_current_context()
        call_logger = self._get_call_logger()

        # Select next API key from pool (round-robin)
        current_key = self.api_keys[self._key_index % len(self.api_keys)] if self.api_keys else ""
        self._key_index += 1
        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json",
        }

        start_time = time.perf_counter()
        response = None
        input_tokens = None
        output_tokens = None
        total_tokens = None
        try:
            response = requests.request("POST", self.url, json=self.payload, headers=headers, timeout=self.timeout)
            latency_s = time.perf_counter() - start_time
            status_code = response.status_code
            reason = response.reason

            # Try to parse usage / tokens if available (nullable telemetry)
            data = None
            try:
                data = json.loads(response.text)
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")
            except Exception:
                data = None

            token_str = ""
            if input_tokens is not None and output_tokens is not None:
                token_str = f" | tokens={input_tokens}+{output_tokens}={total_tokens or (input_tokens + output_tokens)}"

            if response.ok and data and "choices" in data and len(data["choices"]) > 0:
                msg = data["choices"][-1].get("message", {})
                response_content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
                _LOGGER.info(
                    "[LLM] %s <- HTTP %d %s | %.2fs%s",
                    call_id,
                    status_code,
                    reason,
                    latency_s,
                    token_str,
                )
                if call_logger is not None:
                    call_logger.log_attempt(LLMCallRecord(
                        call_id=call_id,
                        worker_id=ctx.worker_id,
                        attempt=attempt,
                        model=self.name,
                        backend=self.backend_name,
                        status_code=status_code,
                        reason=reason,
                        latency_s=latency_s,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        success=True,
                        task_id=ctx.task_id,
                        run_id=ctx.run_id,
                    ))
                return response_content
            else:
                _LOGGER.warning(
                    "[LLM] %s <- HTTP %d %s | %.2fs%s",
                    call_id,
                    status_code,
                    reason,
                    latency_s,
                    token_str,
                )
                if data and "choices" in data and len(data["choices"]) > 0:
                    msg = data["choices"][-1].get("message", {})
                    return msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
                raise RuntimeError(f"HTTP {status_code} {reason}: {response.text}")

        except Exception as exc:
            latency_s = time.perf_counter() - start_time
            status_code = getattr(response, "status_code", None)
            reason = getattr(response, "reason", None)
            if call_logger is not None:
                call_logger.log_attempt(LLMCallRecord(
                    call_id=call_id,
                    worker_id=ctx.worker_id,
                    attempt=attempt,
                    model=self.name,
                    backend=self.backend_name,
                    status_code=status_code,
                    reason=reason,
                    latency_s=latency_s,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    task_id=ctx.task_id,
                    run_id=ctx.run_id,
                ))
            raise

