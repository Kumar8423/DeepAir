#!/usr/bin/env bash
set -euo pipefail


# Default placeholder URL — replace or provide MODEL_URL env var in Vercel project settings
MODEL_URL="${MODEL_URL:-https://your-storage.example.com/path/to/model.pt}"


echo "Fetching model from: $MODEL_URL"


mkdir -p models
curl -L --fail --retry 3 -o models/model.pt "$MODEL_URL"


# If your model is compressed, uncomment and adapt the next lines
# tar -xzf models/model.tar.gz -C models


echo "Model download complete. Contents of models/:"
ls -lh models || true
