FROM python:3.12-slim

WORKDIR /app

# System deps for openpyxl / general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py db_manager.py auth_manager.py ./
COPY .streamlit .streamlit

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080

EXPOSE ${PORT}

# Streamlit must listen on 0.0.0.0 and the Cloud Run PORT
# --server.headless=true  : no browser auto-open
# --server.enableCORS=false : Cloud Run handles CORS
# --server.enableXsrfProtection=false : behind Firebase Hosting proxy
CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
