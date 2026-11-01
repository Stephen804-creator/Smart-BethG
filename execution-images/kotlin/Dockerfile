FROM eclipse-temurin:21-jdk
ARG KOTLIN_VERSION=2.4.21
ARG KOTLIN_SHA256=7cc140e76daf416a0424a5557f99afd7ca89ebd463ea1101261e3e01c33e75cd
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl --fail --location --retry 3 --output /tmp/kotlin-compiler.zip \
       "https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VERSION}/kotlin-compiler-${KOTLIN_VERSION}.zip" \
    && echo "${KOTLIN_SHA256}  /tmp/kotlin-compiler.zip" | sha256sum --check --strict \
    && mkdir -p /opt/kotlin \
    && unzip -q /tmp/kotlin-compiler.zip -d /opt/kotlin \
    && rm -f /tmp/kotlin-compiler.zip
LABEL org.opencontainers.image.title="Smart BethG Kotlin script runtime"
LABEL org.opencontainers.image.licenses="Apache-2.0"
ENV PATH="/opt/kotlin/kotlinc/bin:${PATH}" HOME=/tmp TMPDIR=/tmp
WORKDIR /workspace
USER 65534:65534
ENTRYPOINT []
