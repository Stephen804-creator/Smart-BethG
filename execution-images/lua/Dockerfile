FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends lua5.4 ca-certificates \
    && ln -sf /usr/bin/lua5.4 /usr/local/bin/lua \
    && rm -rf /var/lib/apt/lists/*
LABEL org.opencontainers.image.title="Smart BethG Lua 5.4 script runtime"
LABEL org.opencontainers.image.licenses="MIT"
ENV HOME=/tmp TMPDIR=/tmp
WORKDIR /workspace
USER 65534:65534
ENTRYPOINT []
