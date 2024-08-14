#!/bin/bash

# Check if Conda is installed
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed. Please install Conda and try again."
    exit 1
fi

# Create a new Conda environment
conda create -n llm-discord-bot python=3.9 -y

# Activate the Conda environment
eval "$(conda shell.bash hook)"
conda activate llm-discord-bot

# Install CUDA Toolkit
conda install -c "nvidia/label/cuda-12.1.1" cuda-toolkit cudnn -y

# Set up environment variables
export CUDA_HOME=$CONDA_PREFIX/targets/x86_64-linux
export CUDA_TOOLKIT_INCLUDE_DIR=$CONDA_PREFIX/targets/x86_64-linux/include
export PATH=$CONDA_PREFIX/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Install dependencies
conda install -c conda-forge pip -y
pip install -r requirements.txt

# Install llama-cpp-python with CUDA support
CMAKE_ARGS="-DGGML_CUDA=on -DCUDA_PATH=$CUDA_HOME -DCUDAToolkit_INCLUDE_DIR=$CUDA_TOOLKIT_INCLUDE_DIR" FORCE_CMAKE=1 pip install llama-cpp-python --no-cache-dir

echo "Setup completed successfully!"
echo "To activate this environment, use:"
echo "conda activate llm-discord-bot"
echo "You may need to set these environment variables in your shell:"
echo "export CUDA_HOME=$CONDA_PREFIX"
echo "export PATH=\$CUDA_HOME/bin:\$PATH"
echo "export LD_LIBRARY_PATH=\$CUDA_HOME/lib64:\$LD_LIBRARY_PATH"
