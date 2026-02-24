FROM gnina/gnina:v1.1

# Install python3 + runpod handler
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    && pip3 install --no-cache-dir runpod requests \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY handler.py /app/handler.py

CMD ["python3", "-u", "/app/handler.py"]
