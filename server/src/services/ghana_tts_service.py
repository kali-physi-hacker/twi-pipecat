import asyncio
import base64
import io
import os
import wave
from collections.abc import AsyncGenerator

import numpy as np
import requests
from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService
from pipecat.utils.tracing.service_decorators import traced_tts


class GhanaTTSService(TTSService):
    def __init__(self, settings: TTSSettings, **kwargs):
        super().__init__(**kwargs)
        self._settings: TTSSettings = settings

    async def synthesize(self, text: str):
        response = await asyncio.to_thread(
            requests.post,
            "https://abena.mobobi.com/playground/api/v1/tts/synthesize/",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ['ABENA_KEY']}",
            },
            json={
                "text": text,
                "voice": "abena_twi_high",
            },
        )

        data = response.json()
        # Decode base64 audio
        audio_bytes = base64.b64decode(data["audio_base64"])

        with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
            audio_pcm = wav.readframes(wav.getnframes())
            sample_rate = wav.getframerate()
            num_channels = wav.getnchannels()

        return {"audio_pcm": audio_pcm, "sample_rate": sample_rate, "num_channels": num_channels}

    @traced_tts
    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        """Generate speech from text using using Ghana AudioDiT.

        Args:
            text: The text to synthesize into speech.
            context_id: The context ID for tracking audio frames.

        Yields:
            Frame: Audio frames containing the synthesized speech.
        """
        synthesis = await self.synthesize(text)
        yield TTSAudioRawFrame(
            audio=synthesis["audio_pcm"],
            sample_rate=synthesis["sample_rate"],
            num_channels=synthesis["num_channels"],
            context_id=context_id,
        )
