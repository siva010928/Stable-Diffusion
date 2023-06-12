FROM python:latest

# Install git
RUN apt-get update && apt-get install -y git

# Set the working directory
WORKDIR /app

# Copy the necessary files
COPY cache /app/cache
COPY main.py /app/main.py
COPY audio_files /app/audio_files
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Clone the repository and install the package
RUN pip install git+https://github.com/suno-ai/bark.git

# Set environment variables
ENV XDG_CACHE_HOME=cache/

EXPOSE 8000

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]