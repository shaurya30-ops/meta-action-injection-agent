import asyncio
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import logging
import re
import threading
from pathlib import Path
from content_extraction.extractor_logic import extract_digits
from state_machine.intents import Intent
import config

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# CHILD PROCESS WORKER: Isolated PyTorch space completely outside main GIL
# ══════════════════════════════════════════════════════════════════════

_worker_model = None
_worker_tokenizer = None
_worker_error = None


def _resolve_base_model_source() -> str:
    """
    Prefer a locally cached Hugging Face snapshot so worker startup stays offline.
    Fall back to the repo id if the cache is unavailable.
    """
    try:
        from huggingface_hub import snapshot_download

        return snapshot_download(config.BASE_MODEL_NAME, local_files_only=True)
    except Exception as exc:
        logger.warning(
            "Local snapshot for base model unavailable (%s). Falling back to repo id %s.",
            exc,
            config.BASE_MODEL_NAME,
        )
        return config.BASE_MODEL_NAME


def _is_local_source(source: str) -> bool:
    return Path(source).exists()


def _load_worker_tokenizer(adapter_path: str, base_model_source: str):
    """
    Try the adapter-packaged tokenizer first. If it is corrupted or incompatible,
    fall back to the base Qwen tokenizer instead of failing the whole worker.
    """
    from transformers import AutoTokenizer

    try:
        return AutoTokenizer.from_pretrained(
            adapter_path,
            trust_remote_code=True,
            local_files_only=True,
        )
    except Exception as exc:
        logger.warning(
            "Adapter tokenizer load failed (%s). Falling back to base tokenizer from %s.",
            exc,
            base_model_source,
        )
        tokenizer_kwargs = {"trust_remote_code": True}
        if not _is_local_source(base_model_source):
            tokenizer_kwargs["local_files_only"] = False
        return AutoTokenizer.from_pretrained(base_model_source, **tokenizer_kwargs)


def _init_qwen_process(adapter_path: str):
    """Initializer for the background process. Loads PyTorch and PeftModel here."""
    global _worker_model, _worker_tokenizer, _worker_error
    try:
        import torch
        from transformers import AutoModelForCausalLM
        from peft import PeftModel

        base_model_source = _resolve_base_model_source()
        model_kwargs = {
            "dtype": torch.bfloat16,
            "device_map": "auto",
            "trust_remote_code": True,
        }
        if not _is_local_source(base_model_source):
            model_kwargs["local_files_only"] = False

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_source,
            **model_kwargs,
        )

        _worker_model = PeftModel.from_pretrained(base_model, adapter_path)
        _worker_model.eval()

        _worker_tokenizer = _load_worker_tokenizer(adapter_path, base_model_source)
        if _worker_tokenizer.pad_token is None:
            _worker_tokenizer.pad_token = _worker_tokenizer.eos_token

        # Warm up
        _run_qwen_inference("test")
    except Exception as exc:
        _worker_error = str(exc)


def _run_qwen_inference(transcript: str) -> str:
    """Runs inference inside the background process."""
    global _worker_model, _worker_tokenizer, _worker_error
    if _worker_error:
        raise RuntimeError(f"Worker failed to load model: {_worker_error}")
    
    if _worker_model is None or _worker_tokenizer is None:
        raise RuntimeError("Worker model is not initialized.")

    import torch

    messages = [
        {"role": "system", "content": config.SYSTEM_PROMPT_FOR_CLASSIFIER},
        {"role": "user", "content": transcript},
    ]

    prompt = _worker_tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = _worker_tokenizer(prompt, return_tensors="pt").to(_worker_model.device)

    with torch.no_grad():
        outputs = _worker_model.generate(
            **inputs,
            max_new_tokens=5,
            temperature=0.0,
            do_sample=False,
            pad_token_id=_worker_tokenizer.pad_token_id,
        )

    generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
    return _worker_tokenizer.decode(generated_ids, skip_special_tokens=True).strip().upper()


# ══════════════════════════════════════════════════════════════════════
# MAIN PROCESS: Singleton ProcessPool Manager
# ══════════════════════════════════════════════════════════════════════

# Shared global pool across all call sessions
_global_pool = None
_pool_lock = threading.Lock()

def _get_global_pool(adapter_path: str) -> ProcessPoolExecutor:
    global _global_pool
    with _pool_lock:
        if _global_pool is None:
            logger.info("Starting isolated Global Qwen Process...")
            context = mp.get_context("spawn")
            _global_pool = ProcessPoolExecutor(
                max_workers=1,
                mp_context=context,
                initializer=_init_qwen_process,
                initargs=(adapter_path,)
            )
            # Pre-warm immediately in the background
            _global_pool.submit(_run_qwen_inference, "warmup")
    return _global_pool


class IntentClassifier:
    """
    Classifies Hinglish utterances into one of 15 generic speech-act intents.
    Loads base Qwen2.5-0.5B-Instruct + LoRA adapter inside a ProcessPoolExecutor.
    Falls back to RegexFallbackClassifier if model fails.
    """

    def __init__(self, adapter_path: str = None):
        from .fallback import RegexFallbackClassifier
        self.adapter_path = adapter_path or config.ADAPTER_PATH
        self.valid_intents = set(config.VALID_INTENTS)
        self._fallback = RegexFallbackClassifier()
        # Ensure pool spawns on initialization
        _get_global_pool(self.adapter_path)

    def warmup(self):
        """Blocks until the process pool is fully initialized and warmed up."""
        pool = _get_global_pool(self.adapter_path)
        try:
            pool.submit(_run_qwen_inference, "warmup_sync").result()
        except Exception as e:
            logger.error(f"Failed to load background classifier model (will use API fallback): {e}")

    def _classify_fast_path(self, transcript: str) -> Intent | None:
        normalized = " ".join(transcript.strip().split())
        if not normalized:
            return Intent.UNCLEAR

        extracted_digits = extract_digits(normalized)
        if extracted_digits:
            return Intent.INFORM

        fallback_intent = self._fallback.classify(normalized)
        if fallback_intent == Intent.UNCLEAR:
            if re.search(r"@|at the rate", normalized, re.IGNORECASE):
                return Intent.INFORM
            if re.search(
                r"\b(?:setup|dealer|training|trade|distributor|retail|wholesaler|manufacturer|pharma|medical|business)\b",
                normalized,
                re.IGNORECASE,
            ) and not re.search(
                r"\b(?:kaise|kyun|kya|what|why|how|when|where|who|which|kitna|kitni|kitne|kaun)\b|क्या|कैसे|क्यों",
                normalized,
                re.IGNORECASE,
            ):
                return Intent.INFORM
            return None

        if fallback_intent == Intent.INFORM:
            if extracted_digits or re.search(r"@|at the rate", normalized, re.IGNORECASE):
                return fallback_intent
            return None

        if len(normalized) <= config.CLASSIFIER_FASTPATH_MAX_CHARS:
            return fallback_intent

        return None

    async def classify(self, transcript: str) -> Intent:
        """
        Classify a transcript into an Intent enum.
        Falls back to regex classifier if model is unavailable or errors.
        """
        if not transcript or not transcript.strip():
            return Intent.UNCLEAR

        if fast_path_intent := self._classify_fast_path(transcript):
            logger.info("Classifier fast-pathed transcript to %s", fast_path_intent.value)
            return fast_path_intent

        loop = asyncio.get_running_loop()
        pool = _get_global_pool(self.adapter_path)

        try:
            raw_output = await asyncio.wait_for(
                loop.run_in_executor(pool, _run_qwen_inference, transcript),
                timeout=config.CLASSIFIER_TIMEOUT_SECONDS,
            )

            # Exact match
            if raw_output in self.valid_intents:
                return Intent(raw_output)

            # Fuzzy match (model might output extra tokens)
            for intent_name in self.valid_intents:
                if intent_name in raw_output:
                    return Intent(intent_name)

            logger.warning(f"Model output '{raw_output}' not valid. Using fallback.")
        except asyncio.TimeoutError:
            logger.warning("Classifier timed out. Falling back to OpenAI API...")
        except Exception as e:
            logger.error(f"Process inference failed: {e}. Falling back to OpenAI API...")

        # Fallback to OpenAI API with fast gpt-5.4-nano
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            import openai
            try:
                # Build isolated client to avoid overwriting LiveKit's global client
                import httpx
                http_client = httpx.AsyncClient(verify=False) # In case of local proxy
                openai_client = openai.AsyncOpenAI(api_key=api_key, http_client=http_client)
                
                response = await asyncio.wait_for(openai_client.chat.completions.create(
                    model="gpt-5.4-nano",
                    messages=[
                        {"role": "system", "content": config.SYSTEM_PROMPT_FOR_CLASSIFIER},
                        {"role": "user", "content": transcript}
                    ],
                    max_completion_tokens=5,
                    temperature=0.0
                ), timeout=2.5)
                
                raw_output = response.choices[0].message.content.strip().upper()
                if raw_output in self.valid_intents:
                    return Intent(raw_output)
                for intent_name in self.valid_intents:
                    if intent_name in raw_output:
                        return Intent(intent_name)
            except Exception as e:
                logger.warning(f"OpenAI API Fallback failed: {e}")

        # Final extreme fallback (Regex)
        return self._fallback.classify(transcript)
