FROM python:3.11.9-slim

WORKDIR /app

# Install poetry
RUN pip install poetry \
    && poetry config virtualenvs.create false

# Copy dependency files first
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-root

# Copy source code
COPY . .

# Install the project itself
RUN poetry install --only-root

# Set Python path to include src directory
ENV PYTHONPATH=/app

# Expose the health check port
EXPOSE 8080

# Command to run the application
CMD ["poetry", "run", "python", "-m", "src.main"]
