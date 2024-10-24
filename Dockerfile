FROM python:3.11.9-slim

WORKDIR /app

# Copy source code
COPY . .

# Install dependencies
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install
