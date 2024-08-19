#!/bin/bash

# Check if Conda is installed
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed. Please install Conda and try again."
    exit 1
fi

# Create a new Conda environment
conda create -n llm-discord-bot python=3.12.4 -y

# Activate the Conda environment
eval "$(conda shell.bash hook)"
conda activate llm-discord-bot

# Install dependencies
conda install -c conda-forge pip -y
pip install -r requirements.txt

echo "Setup completed successfully!"
echo "To activate this environment, use:"
echo "conda activate llm-discord-bot"
