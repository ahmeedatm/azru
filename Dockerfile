FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed (e.g. gcc for some python packages)
# Install system dependencies if needed (e.g. gcc for some python packages)
RUN apt-get update && apt-get install -y libgfortran5 && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    chmod -R 755 /usr/local/lib/python3.10/site-packages/gekko/bin

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
