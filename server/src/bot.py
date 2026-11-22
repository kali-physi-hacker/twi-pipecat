import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import numpy as np
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.utils.tracing.service_decorators import traced_tts
from pipecat.workers.runner import WorkerRunner

from services.ghana_tts_service import GhanaTTSService
from tools.transaction import find_transaction

tools = [find_transaction]


# Bot logic
async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)

    MODEL_PATH = Path(__file__).resolve().parent / "models/whisper-twi-v2"
    print(MODEL_PATH)

    # Frame processors
    stt = WhisperSTTService(
        settings=WhisperSTTService.Settings(
            model=str(MODEL_PATH),
            language=None,
        ),
    )
    llm = OpenAILLMService(
        api_key=os.environ["OPENAPI_KEY"],
        settings=OpenAILLMService.Settings(
            model="gpt-4.1",
            max_completion_tokens=150,
            temperature=0.7,
            system_instruction="You are a voice assistant who speaks English and Twi. Keep responses brief.",
        ),
    )
    settings = TTSSettings(model="abena", voice="abena_twi_lite", language="Twi")
    tts = GhanaTTSService(settings)

    # LLm context manager
    context = LLMContext(messages=[], tools=tools)
    aggregators = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            aggregators.user(),
            llm,
            tts,
            transport.output(),
            aggregators.assistant(),
        ]
    )

    # worker (pipeline runner)
    agent = PipelineWorker(
        pipeline,
        name="assistant",
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await runner.cancel()

    await runner.add_workers(agent)
    await runner.run()


transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


# Session Initialization (Listens to users' connection requests)
async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
