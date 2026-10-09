FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt
COPY app ./app
COPY data ./data
COPY examples ./examples
RUN useradd --create-home --uid 10001 coder
USER coder
ENTRYPOINT ["python", "-m", "app.main"]
CMD ["--input", "examples/messy_note.txt"]
