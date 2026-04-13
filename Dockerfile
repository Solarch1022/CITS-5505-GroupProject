FROM python:3.11.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ .

# Create instance directory for SQLite database
RUN mkdir -p /app/instance

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "app.py"]
