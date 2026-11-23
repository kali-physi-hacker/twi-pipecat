import asyncio
import tempfile
import wave
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.services.settings import STTSettings
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601
from pipecat.utils.types import assert_given
from transformers import pipeline


@dataclass
class SimbaSTTSettings(STTSettings):
    """Settings for SimbaSTTService

    Parameters:
        no_speech_prob: Probability threshold for filtering non-speech segments.
    """

    no_speech_prob: float = 0.4


class SimbaSTTService(SegmentedSTTService):
    """Class to transcribe audio with a locally-downloaded Simba model.

    This service uses the simba-s model to perform speech-to-text transcription on audio
    segments.
    """

    def __init__(self, settings: STTSettings, **kwargs):
        super().__init__(**kwargs)
        self._settings: STTSettings = settings
        logger.debug("Loading Simba-S model...")
        self.model = pipeline(
            "automatic-speech-recognition",
            model="UBC-NLP/Simba-S",
        )

    @property
    def wants_wav_segments(self) -> bool:
        return False

    @property
    def segment_sample_rate(self) -> int:
        return 16000

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame | None, None]:
        language = cast("Language | None", assert_given(self._settings.language))

        def transcribe() -> dict:
            with tempfile.TemporaryDirectory() as temp_dir:
                wav_path = Path(temp_dir) / "segment.wav"
                with wave.open(str(wav_path), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)  # 16 bits
                    wav_file.setframerate(self.segment_sample_rate)
                    wav_file.writeframes(audio)

                return self.model(str(wav_path))

        await self.start_processing_metrics()
        result = await asyncio.to_thread(transcribe)
        await self.stop_processing_metrics()

        text = result.get("text", "").strip()
        if text:
            logger.debug(f"Transcription: [{text}]")
            yield TranscriptionFrame(
                text,
                user_id=self._user_id,
                timestamp=time_now_iso8601(),
                language=language,
            )
