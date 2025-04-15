# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV FLASK_APP=bot.py
ENV FLASK_ENV=production

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Run the application with gunicorn
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 bot:app 