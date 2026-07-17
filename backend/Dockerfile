FROM python:3.11-slim
WORKDIR /app

# System deps for Pillow / torch / insightface (needs a C++ compiler to
# build its mesh_core_cython extension) / gfpgan's transitive deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 build-essential && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt

# Install CUDA-enabled PyTorch first.
# --default-timeout / --retries: the CUDA torch wheel is ~750MB+, and pip's
# default 15s *read* timeout (time between chunks, not total download time)
# is too aggressive for that size on anything but a fast, rock-solid
# connection — a brief stall mid-download otherwise kills the whole build
# with a ReadTimeoutError. A long per-read timeout + automatic retries lets
# it ride out normal network hiccups instead of failing the build.
RUN pip install --no-cache-dir \
    --default-timeout=120 --retries 10 \
    torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu126

# Lock in exactly what got installed above, so nothing later can silently
# replace it with a CPU-only build pulled from PyPI.
RUN pip freeze | grep -i '^torch' > /tmp/torch-constraints.txt

# Then install the remaining dependencies, constrained to protect the CUDA torch
RUN pip install --no-cache-dir \
    --default-timeout=120 --retries 10 \
    -r /tmp/requirements.txt -c /tmp/torch-constraints.txt

COPY backend/ /app/
COPY img_prompt.json /img_prompt.json

# Patch basicsr's outdated torchvision import (functional_tensor was removed
# in newer torchvision). Using sed directly on the known site-packages path
# avoids importing basicsr here, since merely importing it triggers the
# same broken import chain we're trying to fix.
RUN sed -i \
    's/from torchvision.transforms.functional_tensor import rgb_to_grayscale/from torchvision.transforms.functional import rgb_to_grayscale/' \
    /usr/local/lib/python3.11/site-packages/basicsr/data/degradations.py

ENV PYTHONUNBUFFERED=1