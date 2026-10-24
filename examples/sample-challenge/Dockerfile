FROM python:3.11-slim

RUN useradd -m -u 1001 appuser

WORKDIR /app

COPY src/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/
RUN chown -R appuser:appuser /app

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

USER appuser

EXPOSE 5000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
