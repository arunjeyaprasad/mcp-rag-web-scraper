FROM mcr.microsoft.com/playwright/python:v1.40.0

# Set environment variable for port
ENV PORT=8090

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE $PORT

# Run the scraper
CMD ["python", "app.py"]
