FROM python:3.11.7-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE $PORT

# Conditional seed logic — run seeder only if RUN_SEED=true
CMD /bin/sh -c "if [ \"$RUN_SEED\" = \"true\" ]; then \
                    echo '🔄 Running database seed...'; \
                    python refresh_db.py; \
                else \
                    echo '➡️ Skipping seed...'; \
                fi && \
                uvicorn main:app --host 0.0.0.0 --port $PORT"
