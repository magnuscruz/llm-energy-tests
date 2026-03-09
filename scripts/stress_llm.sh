#!/bin/bash
MODEL="llama3:8b" # Substitua pelo modelo que baixou

echo "Iniciando teste de aging... (Ctrl+C para parar)"
while true; do
  curl -s -X POST http://localhost:11434/api/generate -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"Descreva detalhadamente o funcionamento de um reator de fusão nuclear.\",
    \"stream\": false
  }" > /dev/null
done
