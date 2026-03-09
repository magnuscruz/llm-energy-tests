# scripts/run_tests.sh addition
echo "Cleaning up background Ollama processes..."
sudo pkill ollama || true
sleep 2
# Start a fresh instance for the test
export OLLAMA_MODELS="/mnt/data/ollama_storage"
ollama serve & 
sleep 5 # Wait for it to boot
