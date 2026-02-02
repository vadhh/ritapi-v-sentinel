FROM python:3.11-slim

# 1. Install System Dependencies
# 'ipset' and 'nftables' are required for the python subprocess calls to work
# 'gcc' and 'python3-dev' are needed to build some python libs
RUN apt-get update && apt-get install -y \
    ipset \
    nftables \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python Dependencies
COPY requirements.txt .
# Removed the manual list since you added them to requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy Source Code
COPY . .

# 4. Set Environment Variables
# Fixes the hardcoded secret issue via ENV injection
ENV PYTHONPATH=/app
ENV MINIFW_SECRET_KEY="docker-change-this-in-prod"

# 5. Default Command (Can be overridden by compose)
CMD ["uvicorn", "app.web.app:app", "--host", "0.0.0.0", "--port", "8000"]