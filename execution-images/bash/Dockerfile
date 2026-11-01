FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*
LABEL org.opencontainers.image.title="Smart BethG Bash script runtime"
ENV HOME=/tmp TMPDIR=/tmp
WORKDIR /workspace
USER 65534:65534
ENTRYPOINT []
