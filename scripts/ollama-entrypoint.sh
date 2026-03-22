#!/bin/bash
# Start Ollama server, wait for it, then pull the model

ollama serve &
OLLAMA_PID=$!

echo "Waiting for Ollama to start..."
until ollama list > /dev/null 2>&1; do
    sleep 1
done
echo "Ollama is ready."

echo "Pulling model: ${OLLAMA_MODEL:-qwen3.5:4b}..."
ollama pull "${OLLAMA_MODEL:-qwen3.5:4b}"
echo "Model ready."

wait $OLLAMA_PID
