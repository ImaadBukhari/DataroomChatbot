# filepath: /Users/imaadbukhari/Documents/DataroomChatbot/backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create tmp directory and copy token file
RUN mkdir -p /tmp
COPY token.json /tmp/token.json

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "app.py"]