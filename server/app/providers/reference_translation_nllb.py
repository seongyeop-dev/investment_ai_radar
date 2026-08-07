from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MODEL_NAME = "facebook/nllb-200-distilled-600M"

SOURCE_LANGUAGE_CODES = {
    "en": "eng_Latn",
    "en-us": "eng_Latn",
    "en-gb": "eng_Latn",
}

TARGET_LANGUAGE_CODES = {
    "ko": "kor_Hang",
}

_HANGUL_PATTERN = re.compile(r"[\uac00-\ud7a3]")

_LATIN_PATTERN = re.compile(r"[A-Za-z]")

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")

_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class KoreanTranslationQuality:
    passed: bool
    hangul_count: int
    latin_count: int
    cjk_count: int
    letter_count: int
    hangul_ratio: float
    reasons: tuple[str, ...]


def evaluate_korean_translation(
    source_text: str,
    translated_text: str,
) -> KoreanTranslationQuality:
    source = source_text.strip()
    translated = translated_text.strip()

    hangul_count = len(_HANGUL_PATTERN.findall(translated))
    latin_count = len(_LATIN_PATTERN.findall(translated))
    cjk_count = len(_CJK_PATTERN.findall(translated))

    letter_count = hangul_count + latin_count + cjk_count

    hangul_ratio = hangul_count / letter_count if letter_count else 0.0

    reasons: list[str] = []

    if not translated:
        reasons.append("EMPTY_RESULT")

    if source and translated.casefold() == source.casefold():
        reasons.append("UNCHANGED_SOURCE")

    if hangul_count < 2:
        reasons.append("INSUFFICIENT_HANGUL")

    if hangul_ratio < 0.35:
        reasons.append("LOW_HANGUL_RATIO")

    if "\ufffd" in translated:
        reasons.append("REPLACEMENT_CHARACTER")

    if _CONTROL_PATTERN.search(translated):
        reasons.append("CONTROL_CHARACTER")

    if source and len(translated) > max(500, len(source) * 8):
        reasons.append("EXCESSIVE_OUTPUT_LENGTH")

    return KoreanTranslationQuality(
        passed=not reasons,
        hangul_count=hangul_count,
        latin_count=latin_count,
        cjk_count=cjk_count,
        letter_count=letter_count,
        hangul_ratio=hangul_ratio,
        reasons=tuple(reasons),
    )


class LocalNllbTranslationProvider:
    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL_NAME,
        cache_dir: Path | None = None,
        local_files_only: bool = False,
        max_source_tokens: int = 256,
        max_new_tokens: int = 128,
        num_beams: int = 5,
    ) -> None:
        normalized_model_name = model_name.strip()

        if not normalized_model_name:
            raise ValueError("model_name must not be empty")

        if max_source_tokens < 1:
            raise ValueError("max_source_tokens must be at least 1")

        if max_source_tokens > 512:
            raise ValueError("max_source_tokens must not exceed 512")

        if max_new_tokens < 1:
            raise ValueError("max_new_tokens must be at least 1")

        if num_beams < 1:
            raise ValueError("num_beams must be at least 1")

        self.model_name = normalized_model_name
        self.cache_dir = cache_dir.resolve() if cache_dir is not None else None
        self.local_files_only = local_files_only
        self.max_source_tokens = max_source_tokens
        self.max_new_tokens = max_new_tokens
        self.num_beams = num_beams

        self.name = f"local-nllb:{self.model_name}"

        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._torch: Any | None = None
        self._source_code: str | None = None
        self._target_code: str | None = None
        self._target_token_id: int | None = None

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

        source_code = self._source_code_for(source_language)
        target_code = self._target_code_for(target_language)

        (
            tokenizer,
            model,
            torch,
            target_token_id,
        ) = self._load(
            source_code=source_code,
            target_code=target_code,
        )

        encoded = tokenizer(
            normalized_text,
            return_tensors="pt",
            truncation=True,
            max_length=(self.max_source_tokens),
        )

        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                forced_bos_token_id=(target_token_id),
                max_new_tokens=(self.max_new_tokens),
                num_beams=self.num_beams,
                do_sample=False,
                early_stopping=True,
                no_repeat_ngram_size=3,
            )

        decoded = tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        if not decoded:
            raise RuntimeError("NLLB returned no generated result")

        translated = decoded[0].strip()

        if not translated:
            raise RuntimeError("NLLB returned an empty result")

        return translated

    @staticmethod
    def _source_code_for(
        language: str,
    ) -> str:
        normalized = language.strip().lower()

        try:
            return SOURCE_LANGUAGE_CODES[normalized]
        except KeyError as exc:
            raise ValueError("NLLB provider supports only English source text") from exc

    @staticmethod
    def _target_code_for(
        language: str,
    ) -> str:
        normalized = language.strip().lower()

        try:
            return TARGET_LANGUAGE_CODES[normalized]
        except KeyError as exc:
            raise ValueError("NLLB provider supports only Korean target text") from exc

    def _load(
        self,
        *,
        source_code: str,
        target_code: str,
    ) -> tuple[Any, Any, Any, int]:
        if (
            self._tokenizer is not None
            and self._model is not None
            and self._torch is not None
            and self._source_code == source_code
            and self._target_code == target_code
            and self._target_token_id is not None
        ):
            return (
                self._tokenizer,
                self._model,
                self._torch,
                self._target_token_id,
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

        load_options: dict[
            str,
            object,
        ] = {
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
            src_lang=source_code,
            tgt_lang=target_code,
            **load_options,
        )

        target_token_id = tokenizer.convert_tokens_to_ids(target_code)

        if target_token_id is None or target_token_id == tokenizer.unk_token_id:
            raise RuntimeError(f"NLLB target language token was not found: {target_code}")

        model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_name,
            **load_options,
        )

        model.to("cpu")
        model.eval()

        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch
        self._source_code = source_code
        self._target_code = target_code
        self._target_token_id = int(target_token_id)

        return (
            tokenizer,
            model,
            torch,
            int(target_token_id),
        )
