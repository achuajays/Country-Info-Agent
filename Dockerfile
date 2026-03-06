# Use a lightweight Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PATH="/app/.venv/bin:$PATH"

# Set the working directory
WORKDIR /app

# Install uv for extremely fast, reliable dependency installation
RUN pip install --no-cache-dir uv

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into an isolated virtual environment
RUN uv sync --frozen --no-install-project

# Copy the rest of the application code
COPY . .

# Expose the port that Uvicorn will listen on
EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
