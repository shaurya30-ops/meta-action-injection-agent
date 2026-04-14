import asyncio
import torch
import logging
import threading
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from state_machine.intents import Intent
import config

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    Classifies Hinglish utterances into one of 15 generic speech-act intents.
    Loads base Qwen2.5-0.5B-Instruct + LoRA adapter for inference.
    Falls back to RegexFallbackClassifier if model fails.
    """

    def __init__(self, adapter_path: str = None):
        self.adapter_path = adapter_path or config.ADAPTER_PATH
        self.valid_intents = set(config.VALID_INTENTS)
        self._model = None
        self._tokenizer = None
        self._fallback = None
        self._loaded = False
        self._model_lock = threading.Lock()

    def _load(self):
        """Lazy-load model on first classify call. Keeps startup fast."""
        if self._loaded:
            return

        from .fallback import RegexFallbackClassifier
        self._fallback = RegexFallbackClassifier()

        try:
            logger.info(f"Loading base model: {config.BASE_MODEL_NAME}")
            base_model = AutoModelForCausalLM.from_pretrained(
                config.BASE_MODEL_NAME,
                dtype=torch.bfloat16,
                device_map="auto",
                trust_remote_code=True,
            )

            logger.info(f"Loading LoRA adapter: {self.adapter_path}")
            self._model = PeftModel.from_pretrained(base_model, self.adapter_path)
            self._model.eval()

            self._tokenizer = AutoTokenizer.from_pretrained(self.adapter_path)
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            # Warm up with dummy inference
            self._classify_raw("test")
            logger.info("Intent classifier loaded and warmed up")

        except Exception as e:
            logger.error(f"Failed to load LoRA adapter: {e}. Using fallback classifier.")
            self._model = None

        self._loaded = True

    def _load_threadsafe(self) -> None:
        with self._model_lock:
            self._load()

    def _classify_raw(self, transcript: str) -> str:
        """Run raw model inference. Returns the cleaned label string."""
        messages = [
            {"role": "system", "content": config.SYSTEM_PROMPT_FOR_CLASSIFIER},
            {"role": "user", "content": transcript},
        ]

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=5,
                temperature=0.0,
                do_sample=False,
                pad_token_id=self._tokenizer.pad_token_id,
            )

        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(generated_ids, skip_special_tokens=True).strip().upper()

    def _classify_raw_threadsafe(self, transcript: str) -> str:
        with self._model_lock:
            return self._classify_raw(transcript)

    async def classify(self, transcript: str) -> Intent:
        """
        Classify a transcript into an Intent enum.
        Falls back to regex classifier if model is unavailable or errors.
        """
        if not transcript or not transcript.strip():
            return Intent.UNCLEAR

        loop = asyncio.get_running_loop()

        if not self._loaded:
            await loop.run_in_executor(None, self._load_threadsafe)

        # Try LoRA model
        if self._model is not None:
            try:
                raw_output = await asyncio.wait_for(
                    loop.run_in_executor(None, self._classify_raw_threadsafe, transcript),
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
                logger.warning("Classifier timed out. Using fallback.")
            except Exception as e:
                logger.error(f"Model inference failed: {e}. Using fallback.")

        # Fallback to regex
        return self._fallback.classify(transcript)
