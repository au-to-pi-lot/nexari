#!/bin/bash

# Check if Conda is installed
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed. Please install Conda and try again."
    exit 1
fi

# Create a new Conda environment
conda create -n llm-discord-bot python=3.9 -y

# Activate the Conda environment
conda activate llm-discord-bot

# Install CUDA Toolkit
conda install -c nvidia cuda-toolkit cudnn -y

# Set up environment variables
export CUDA_HOME=$CONDA_PREFIX
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Install dependencies
conda install -c conda-forge pip -y
pip install -r requirements.txt

# Install llama-cpp-python with CUBLAS support
CMAKE_ARGS="-DLLAMA_CUBLAS=on" FORCE_CMAKE=1 pip install llama-cpp-python --no-cache-dir

echo "Setup completed successfully!"
echo "To activate this environment, use:"
echo "conda activate llm-discord-bot"
echo "You may need to set these environment variables in your shell:"
echo "export CUDA_HOME=$CONDA_PREFIX"
echo "export PATH=\$CUDA_HOME/bin:\$PATH"
echo "export LD_LIBRARY_PATH=\$CUDA_HOME/lib64:\$LD_LIBRARY_PATH"
