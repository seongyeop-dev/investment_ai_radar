from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_MODEL_NAME = "Helsinki-NLP/opus-mt-tc-big-en-ko"


class LocalMarianTranslationProvider:
    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL_NAME,
        cache_dir: Path | None = None,
        local_files_only: bool = False,
        max_source_tokens: int = 256,
        max_new_tokens: int = 256,
    ) -> None:
        normalized_model_name = model_name.strip()

        if not normalized_model_name:
            raise ValueError("model_name must not be empty")

        if max_source_tokens < 1:
            raise ValueError("max_source_tokens must be at least 1")

        if max_new_tokens < 1:
            raise ValueError("max_new_tokens must be at least 1")

        self.model_name = normalized_model_name
        self.cache_dir = cache_dir.resolve() if cache_dir is not None else None
        self.local_files_only = local_files_only
        self.max_source_tokens = max_source_tokens
        self.max_new_tokens = max_new_tokens

        self.name = f"local-marian:{self.model_name}"

        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._torch: Any | None = None

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> str:
        normalized_text = text.strip()

        if not normalized_text:
            return ""

        source = source_language.strip().lower()
        target = target_language.strip().lower()

        if source not in {
            "en",
            "en-us",
            "en-gb",
        }:
            raise ValueError("Local Marian provider supports only English source text")

        if target != "ko":
            raise ValueError("Local Marian provider supports only Korean target text")

        tokenizer, model, torch = self._load()

        encoded = tokenizer(
            normalized_text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_source_tokens,
        )

        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                max_new_tokens=(self.max_new_tokens),
                num_beams=4,
                do_sample=False,
                early_stopping=True,
            )

        decoded = tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        if not decoded:
            raise RuntimeError("Translation model returned no generated result")

        translated = decoded[0].strip()

        if not translated:
            raise RuntimeError("Translation model returned an empty result")

        return translated

    def _load(
        self,
    ) -> tuple[Any, Any, Any]:
        if self._tokenizer is not None and self._model is not None and self._torch is not None:
            return (
                self._tokenizer,
                self._model,
                self._torch,
            )

        try:
            import torch
            from transformers import (
                AutoModelForSeq2SeqLM,
                AutoTokenizer,
            )
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Local translation dependencies "
                "are not installed. Enable the "
                "'translation-local' extra."
            ) from exc

        load_options: dict[str, object] = {
            "local_files_only": (self.local_files_only),
        }

        if self.cache_dir is not None:
            self.cache_dir.mkdir(
                parents=True,
                exist_ok=True,
            )
            load_options["cache_dir"] = str(self.cache_dir)

        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            **load_options,
        )

        model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_name,
            **load_options,
        )

        model.to("cpu")
        model.eval()

        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch

        return tokenizer, model, torch
