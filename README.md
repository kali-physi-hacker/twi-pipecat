# Pipecat Twi Voice Assistant

A Pipecat voice assistant that supports English and Twi. It uses a local Whisper
model for speech-to-text, OpenAI GPT-4.1 for responses and function calling,
and Abena's Ghana AudioDiT service for Twi text-to-speech.

## Configuration

- **Bot type:** Web
- **Transport:** WebRTC
- **Pipeline:** Cascade
  - **STT:** Local Whisper (`whisper-twi-v2`)
  - **LLM:** OpenAI GPT-4.1
  - **TTS:** Abena/Ghana AudioDiT
- **Features:** Live conversation, Silero VAD, Twi responses, transaction lookup,
  live metrics, behavioral evals, and Pipecat Cloud deployment

## Prerequisites

- Python 3.11-3.14
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- API credentials:
  - `OPENAPI_KEY` for the OpenAI LLM
  - `ABENA_KEY` for Ghana/Abena TTS
- Microphone access in a browser

The server currently requires macOS-compatible ML dependencies only for local
development with the included environment. The Docker image builds on Linux and
the bundled Whisper model is copied or downloaded during the image build.

## Setup

Run the server and client in separate terminals.

### 1. Configure the server

```bash
cd server
cp .env.example .env
uv sync
```

Edit `server/.env` and set:

```dotenv
OPENAPI_KEY=your-openai-api-key
ABENA_KEY=your-abena-api-key
```

The `.env` file is git-ignored. Never commit real provider credentials.

### 2. Start the server

```bash
cd server
uv run src/bot.py
```

The Pipecat runner serves the WebRTC bot on `http://localhost:7860` by default.
Keep this process running while using the client or running eval scenarios.

The Whisper model is loaded from
`server/src/models/whisper-twi-v2/model.bin`. Docker builds use the bundled
model when it is present, or download and convert
`tiffany101/whisper-twi-v2` when it is not.

### 3. Configure and start the client

```bash
cd client
npm install
cp env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

> **Current transport note:** the client configuration is set to LiveKit, while
> `server/src/bot.py` currently declares a `webrtc` transport entry. Align the
> client and server before using the browser connection flow. For WebRTC, update
> the client to use the `smallwebrtc` transport or change the server transport
> configuration to match LiveKit. The LiveKit setup will require the applicable
> LiveKit credentials and server transport parameters.

The client sends connection requests to `/api/start`, which forwards them to
`http://localhost:7860/start` by default. The optional client environment
variables are:

```dotenv
BOT_START_URL=http://localhost:7860/start
BOT_START_PUBLIC_API_KEY=
```

Set `BOT_START_URL` to the public bot start endpoint when using a remote or
deployed server. Set `BOT_START_PUBLIC_API_KEY` only if that endpoint requires
Bearer authentication.

## How the bot works

The server builds a Pipecat cascade pipeline:

```text
WebRTC input
  -> local Whisper STT
  -> user context aggregator
  -> OpenAI GPT-4.1
  -> Abena Twi TTS
  -> WebRTC output
  -> assistant context aggregator
```

The `find_transaction` tool accepts a Twi or English transcript, extracts a
Cedis amount and Ghanaian phone number, and checks a demo transaction database.
It reports missing information, no match, or the transaction status to the LLM.
The demo lookup is in `server/src/tools/transaction.py`; replace it with your
real transaction backend before production use.

## Testing with evals

The project includes behavioral eval scenarios. Scenarios drive the bot through
the Pipecat runner, so no live voice call is needed for the text-mode loop.

Start the bot in one terminal:

```bash
cd server
uv run src/bot.py
```

Run a scenario in a second terminal:

```bash
cd server
uv run pipecat eval run evals/starter_text.yaml -v
uv run pipecat eval run evals/starter_audio.yaml -v
```

- Text mode is the fast loop for prompt behavior and function-call decisions.
- Audio mode exercises VAD, STT, TTS, and the full round trip.
- The starter audio scenario downloads local speech models on the first run.

Some eval assertions use a judge LLM. The scenario files default to local
Ollama with `gemma4:12b`:

```bash
ollama pull gemma4:12b
```

The eval files may instead be configured to use OpenAI or another supported
judge provider. Add scenarios under `server/evals/` as bot behavior changes.

## Project structure

```text
pipecat-twi/
├── server/
│   ├── src/
│   │   ├── bot.py                    # Main Pipecat worker and pipeline
│   │   ├── models/whisper-twi-v2/   # Bundled Whisper model
│   │   ├── services/
│   │   │   └── ghana_tts_service.py # Abena TTS implementation
│   │   └── tools/
│   │       └── transaction.py       # Demo transaction lookup tool
│   ├── evals/                        # Text and audio eval scenarios
│   ├── .env.example                  # Server environment template
│   ├── Dockerfile                    # Pipecat Cloud/container image
│   ├── pcc-deploy.toml               # Pipecat Cloud deployment settings
│   ├── pyproject.toml                # Python dependencies
│   └── uv.lock                       # Reproducible Python dependencies
├── client/
│   ├── src/app/                      # Next.js pages and /api/start route
│   ├── src/components/pipecat/       # Pipecat UI components
│   ├── src/hooks/                    # Client, metrics, and event hooks
│   ├── env.example                   # Client environment template
│   └── package.json                  # Node dependencies and scripts
└── README.md
```

## Building and testing the client

```bash
cd client
npm run dev
npm run lint
npm run build
npm run start
```

The client uses Next.js and the Pipecat UI console components. These components
live under `client/src/components/pipecat/` and may be edited directly.

## Deploying with Docker

The server Dockerfile uses `dailyco/pipecat-base:latest-py3.14`, syncs locked
dependencies, copies `server/src`, and bundles or converts the Whisper model.

Build and run from `server/`:

```bash
cd server
docker build -t twi-voice-assistant .
docker run --rm -p 7860:7860 \
  --env-file .env \
  twi-voice-assistant
```

When deploying outside Docker, inject `OPENAPI_KEY` and `ABENA_KEY` through the
host's secret manager rather than copying `.env` into an image.

## Deploying to Pipecat Cloud

This project includes `server/pcc-deploy.toml`:

```toml
agent_name = "twi-project"
secret_set = "twi-project-secrets"
agent_profile = "agent-1x"
```

Before deploying:

1. Create a Pipecat Cloud account and complete `pipecat cloud auth login`.
2. Put the server secrets in `server/.env`.
3. Create the configured secret set:

   ```bash
   cd server
   pipecat cloud secrets set twi-project-secrets --file .env --skip
   pipecat cloud deploy --yes
   ```

Do not include real credentials in `pcc-deploy.toml` or source control.

See the [Pipecat Cloud documentation](https://docs.pipecat.ai/pipecat-cloud/introduction)
for account setup and ongoing agent management.

## Security and production readiness

- Rotate provider credentials if they have ever been committed or shared.
- The transaction database is in-memory and contains demo data only.
- The bot can speak and act on unverified caller requests; add authentication,
  authorization, rate limits, redaction, and audit logging before production.
- Never collect or log PINs or other sensitive authentication credentials.

## Learn more

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat UI Documentation](https://ui.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Pipecat Discord](https://discord.gg/pipecat)
