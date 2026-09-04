FROM python:3.12-slim

WORKDIR /app
COPY src ./src
ENV PYTHONPATH=/app/src

RUN useradd --create-home monitor && mkdir -p /app/data && chown -R monitor:monitor /app
USER monitor

EXPOSE 8080
CMD ["python", "-m", "yc_launch_monitor", "serve"]
