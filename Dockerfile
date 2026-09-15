FROM python:3.12-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY capoeira_agent ./capoeira_agent
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

ENV CAPOEIRA_AGENT_BASE_URL=http://host.docker.internal:8765

VOLUME ["/workspace"]
ENTRYPOINT ["capoeira-agent"]
CMD ["/workspace"]