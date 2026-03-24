FROM python:3.11-slim

# iputils-ping provides the ping binary
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY config.py bridge.py ./

CMD ["python", "bridge.py", "--loop"]
