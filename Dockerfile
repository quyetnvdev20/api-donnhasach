# Build stage
FROM python:3.9 as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    apt-get install -y ffmpeg libsm6 libxext6 alien libaio1 && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Final stage
FROM python:3.9

# Create non-root user for security
RUN addgroup --system app && adduser --system --group app

WORKDIR /app

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 alien libaio1
# Copy application code
COPY . .
COPY reference_full.jpg /app/reference_full.jpg

# Set ownership to non-root user
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Expose port
EXPOSE 8000

# Run migrations and start application using Gunicorn
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8000