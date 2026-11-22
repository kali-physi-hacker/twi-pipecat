import asyncio
import io
import os
from collections.abc import AsyncGenerator

import requests
import soundfile as sf
from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService
from pipecat.utils.tracing.service_decorators import traced_tts

BASE = "https://notevibes.com/api/tts"


class NotevibesTTSService(TTSService):
    def __init__(self, settings: TTSSettings, **kwargs):
        super().__init__(**kwargs)
        self._settings: TTSSettings = settings

    async def synthesize(self, text: str):
        headers = {
            "Authorization": f"Bearer {os.environ['NOTEVIBES_API_KEY']}",
        }

        # Create the job
        response = await asyncio.to_thread(
            requests.post,
            BASE + "/create",
            headers=headers,
            json={
                "title": "text",
                "content": text,
                "voice": "ak-GH-Chirp3-HD-Algenib",
            },
        )

        if not response.ok:
            raise RuntimeError(f"{response.status_code}: {response.json().get('error')}")
        job_id = response.json()["jobId"]

        # 2. Poll until the job is done
        while True:
            await asyncio.sleep(0.25)
            poll = await asyncio.to_thread(
                requests.get,
                f"{BASE}/jobs/{job_id}",
                headers=headers,
            )
            if not poll.ok:
                raise RuntimeError(f"{poll.status_code}: {poll.json().get('error')}")
            job = poll.json()
            if job["status"] in ("completed", "failed"):
                break

        if job["status"] == "failed":
            raise RuntimeError("Job failed: " + job["error"])

        # Download and decode the audio in memory.
        audio = await asyncio.to_thread(requests.get, job["result"]["audioUrl"])
        audio.raise_for_status()

        audio_pcm_array, sample_rate = await asyncio.to_thread(
            sf.read,
            io.BytesIO(audio.content),
            dtype="int16",
            always_2d=True,
        )
        audio_pcm = audio_pcm_array.tobytes()
        num_channels = audio_pcm_array.shape[1]

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
