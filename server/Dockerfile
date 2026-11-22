FROM dailyco/pipecat-base:latest-py3.14

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Uncomment if you wish to print a summary of the features available in the base image
# ENV PCC_LOG_FEATURES_SUMMARY=true

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy the application code
COPY ./src src
# Download and convert the STT model from HF
RUN --mount=type=cache,target=/root/.cache/huggingface \
    if [ -f src/models/whisper-twi-v2/model.bin ]; then \
    echo "Using bundled Whisper model"; \
    else \
    ct2-transformers-converter \
    --model tiffany101/whisper-twi-v2 \
    --output_dir src/models/whisper-twi-v2 \
    --copy_files tokenizer.json preprocessor_config.json; \
    fi
CMD ["python", "src/bot.py", "-t", "webrtc", "--host", "0.0.0.0", "--port", "7860"]