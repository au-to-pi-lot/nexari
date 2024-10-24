FROM python:3.11.9-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy source code
COPY . .

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install

# Install project
RUN poetry install
