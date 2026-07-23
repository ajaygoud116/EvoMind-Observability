FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY evomind/ evomind/

EXPOSE 8000

CMD ["python", "-m", "evomind"]
