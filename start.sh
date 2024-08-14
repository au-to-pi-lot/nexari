#!/bin/bash

# Activate the Conda environment
eval "$(conda shell.bash hook)"
conda activate llm-discord-bot

# Run the main.py script
python main.py
