from nikolasigmoid/py-mcp-proxy:latest

# Install dependencies and Chromium (cross-arch compatible)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    xvfb \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROXY_SCOPE="*api.dune.com*"
copy main.py .
copy utils .
run echo "{\"command\": \"python\", \"args\": [\"-c\", \"from main import mcp; mcp.run()\"]}" > config.json
