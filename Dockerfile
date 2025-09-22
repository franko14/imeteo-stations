FROM python:3.12-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Set the entrypoint to the CLI
ENTRYPOINT ["imeteo"]

# Default command shows help
CMD ["--help"]