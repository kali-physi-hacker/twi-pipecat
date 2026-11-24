import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import numpy as np
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import Frame, LLMRunFrame, TTSAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.dtmf_aggregator import DTMFAggregator
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import DailyDialinRequest, RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.settings import STTSettings, TTSSettings
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyDialinSettings, DailyParams, DailyTransport
from pipecat.utils.tracing.service_decorators import traced_tts
from pipecat.workers.runner import WorkerRunner

from src.services.ghana_tts_service import GhanaTTSService
from src.services.notevibes_tts_service import NotevibesTTSService
from src.services.simba_stt_service import SimbaSTTService, SimbaSTTSettings
from src.tools.accounts import find_user_id, get_account_balance, get_account_type
from src.tools.transaction import find_transaction, get_sum

tools = [
    find_transaction,
    get_sum,
    get_account_balance,
    get_account_type,
    find_user_id,
]

# Keep the original method
_original_handle_dialin_ready = DailyTransport._handle_dialin_ready


async def patched_handle_dialin_ready(self, sip_endpoint):
    # Convert the dictionary into the SIP URI string
    if isinstance(sip_endpoint, dict):
        sip_endpoint = sip_endpoint["sipEndpoint"]

    # Call Pipecat's original implementation
    await _original_handle_dialin_ready(self, sip_endpoint)


# Replace the class method at runtime
DailyTransport._handle_dialin_ready = patched_handle_dialin_ready


# Bot logic
async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting bot")

    # Frame processors
    stt = SimbaSTTService(settings=SimbaSTTSettings(model="simba-s", language="twi"))

    llm = OpenAILLMService(
        api_key=os.environ["OPENAPI_KEY"],
        settings=OpenAILLMService.Settings(
            model="gpt-4.1",
            max_completion_tokens=150,
            temperature=0.7,
            system_instruction="You are a voice assistant who understands English and Twi. For this round only, repeat your self-introduction in both languages. Afterwards, stick to the language user speaks or specifically asks for. If the user asks for any other language, politely decline saying you can only reliably operate in the two languages. If the user asks for a specific question (not a mere greeting) that is not related to any finance-related functionalities you have access to, tell the user that you do not have access to that information and prompt them to ask about their transactions. The Twi speech-to-text system is premature and may contain typos. In particular, e nad o are often swapped with ɛ and ɔ, respectively, and vice versa. A word may be split into multiple words, and words might be transcribed as one word. Be generous about interpreting it, and aks clarifying questions. If transaction speech is unclear, ask the user to enter one phone number or amount at a time on the keypad and press #. Keypad input appears as 'DTMF: <digits>#'; use it for the value requested (amounts are cedis). Keep responses brief.",
        ),
    )
    settings = TTSSettings(model="Notevibes", voice="ak-GH-Chirp3-HD-Algenib", language="Twi")
    tts = NotevibesTTSService(settings)

    # LLm context manager
    context = LLMContext(messages=[], tools=tools)
    aggregators = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    dtmf_aggregator = DTMFAggregator(timeout=10.0)

    pipeline = Pipeline(
        [
            transport.input(),
            dtmf_aggregator,
            stt,
            aggregators.user(),
            llm,
            tts,
            transport.output(),
            aggregators.assistant(),
        ]
    )

    # worker (pipeline runner)
    worker = PipelineWorker(
        pipeline,
        name="assistant",
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)

    await runner.add_workers(worker)

    # Start speaking when caller joins
    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        logger.debug(f"First participant joined: {participant['id']}")
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await runner.cancel()

    @transport.event_handler("on_dialin_ready")
    async def on_dialin_ready(transport, sip_endpoint):
        logger.info(f"Dial-in ready: {sip_endpoint['sipEndpoint']}")

    @transport.event_handler("on_dialin_connected")
    async def on_dialin_connected(transport, data):
        logger.info(f"Dial-in connected: {data}")

    @transport.event_handler("on_dialin_stopped")
    async def on_dialin_stopped(transport, data):
        logger.info(f"Dial-in stopped: {data}")
        await runner.cancel()

    @transport.event_handler("on_dialin_warning")
    async def on_dialin_warning(transport, data):
        logger.warning(f"Dial-in warning: {data}")

    @transport.event_handler("on_dialin_error")
    async def on_dialin_error(transport, data):
        logger.error(f"Dial-in error: {data}")
        await runner.cancel()

    @transport.event_handler("on_dtmf_event")
    async def on_dtmf_event(transport, data):
        logger.info(f"DTMF event: {data}")

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        # Kick off the conversation
        context.add_message(
            {
                "role": "developer",
                "content": """
                Start by concisely identifying yourself as a Twi-English voice assistent at the Bank of Minervapolis, and asking for the user's preferred language.
                """,
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    await runner.run()


# Session Initialization (Listens to users' connection requests)
async def bot(runner_args: RunnerArguments):
    """Main bot entry point."""
    transport_params = {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
        "daily": lambda: DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    }

    transport = await create_transport(runner_args, transport_params)

    # Optional: personalize using the dial-in request (which number called, which
    # number was dialed).
    if isinstance(runner_args.body, dict) and "dialin_settings" in runner_args.body:
        request = DailyDialinRequest.model_validate(runner_args.body)
        if request.dialin_settings.From:
            logger.info(f"Handling call from: {request.dialin_settings.From}")
        if request.dialin_settings.To:
            logger.info(f"Handling call to: {request.dialin_settings.To}")

    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
