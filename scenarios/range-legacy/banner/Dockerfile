# Banner-only socket: accepts a TCP connection, writes $BANNER, closes.
# No service logic - it exists so the range presents a fingerprintable port.
FROM python:3.12-alpine
COPY banner.py /banner.py
ENV PORT=9000
EXPOSE 9000
ENTRYPOINT ["python", "/banner.py"]
