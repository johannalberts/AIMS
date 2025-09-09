FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Change the working directory to the `app` directory
WORKDIR /app

# Copy the lockfile and `pyproject.toml` into the image
COPY uv.lock pyproject.toml ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy the project into the image
COPY . .

# Sync the project
RUN uv sync --frozen --no-cache

# Expose the port that the application listens on
EXPOSE 8000

# Run the application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]