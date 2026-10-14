ARG BASE_IMAGE=ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36
FROM ${BASE_IMAGE} AS build
ARG LLAMA_REVISION=4413a192410fad1f054e9216114087a3e01527a0
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends g++ cmake make curl ca-certificates \
    && curl -fL "https://codeload.github.com/ggml-org/llama.cpp/tar.gz/${LLAMA_REVISION}" -o /tmp/source.tar.gz \
    && mkdir /src \
    && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /src \
    && cmake -S /src -B /build \
       -DGGML_NATIVE=OFF -DGGML_SSE42=ON -DGGML_BMI2=OFF \
       -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_AVX512=OFF \
       -DGGML_FMA=OFF -DGGML_F16C=OFF \
       -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF \
    && cmake --build /build --target llama-server -j2

FROM ${BASE_IMAGE}
COPY --from=build /build/bin/ /opt/llama/
COPY --from=build /usr/lib/x86_64-linux-gnu/libgomp.so.1 /opt/llama/libgomp.so.1
COPY --from=build /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /opt/llama/libstdc++.so.6
ENV LD_LIBRARY_PATH=/opt/llama
USER 65534:65534
ENTRYPOINT ["/opt/llama/llama-server"]
