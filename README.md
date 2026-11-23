# Pipecat Twi Voice Assistant

A web voice assistant for English and Twi, built with [Pipecat](https://docs.pipecat.ai/).

The server runs a cascade voice pipeline with custom Simba STT and Notevibes TTS
services. The Next.js client provides the browser console, while the server also
supports Daily transport and dial-in events.

## Features

- English and Twi voice conversations
- SmallWebRTC browser connections
- Daily transport and dial-in event handling
- Custom Simba STT integration
- Custom Notevibes TTS integration
- OpenAI GPT-4.1 responses and function calling
- Transaction lookup by amount and Ghanaian phone number
- Transaction totals by phone number and optional time range
- Silero VAD
- Pipeline and usage metrics
- Text and audio Pipecat evaluation scenarios
- Pipecat Cloud deployment configuration

The transaction data is demo data loaded from
`server/src/database/transactions.csv`. It is held in memory and is not
suitable for production use.

## Architecture

```text
Browser microphone
  -> SmallWebRTC client
  -> Pipecat transport input
  -> Simba STT service
  -> user context aggregator
  -> OpenAI GPT-4.1
  -> Notevibes TTS service
  -> Pipecat transport output
  -> browser audio
  -> assistant context aggregator
