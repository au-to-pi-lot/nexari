#!/bin/bash

# Check if Conda is installed
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed. Please install Conda and try again."
    exit 1
fi

# Create a new Conda environment
conda create -n llm-discord-bot python=3.9 -y

# Activate the Conda environment
source activate llm-discord-bot

# Install CUDA Toolkit
conda install -c nvidia cuda-toolkit -y

# Install dependencies
conda install -c conda-forge pip -y
pip install -r requirements.txt

# Install llama-cpp-python with CUBLAS support
CMAKE_ARGS="-DGGML_CUDA=on" FORCE_CMAKE=1 pip install llama-cpp-python --force-reinstall --upgrade --no-cache-dir

echo "Setup completed successfully!"
echo "To activate this environment, use:"
echo "conda activate llm-discord-bot"
