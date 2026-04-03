FROM python:3.11-slim

# HuggingFace Spaces requires a non-root user with uid 1000
RUN useradd -m -u 1000 user

WORKDIR /app

# Install dependencies as root first
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY --chown=user . .

# Switch to non-root user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
