# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0


FROM ubuntu:22.04 AS build

# setup the build box
ARG DEBIAN_FRONTEND=noninteractive
# get platform and put in env variable

RUN apt-get update && \
  apt-get -y upgrade && \
  apt-get install -yq curl vim jq uuid-runtime git make net-tools gcc ca-certificates wget && rm -rf /var/cache/apt/archives /var/lib/apt/lists/*

# install go1.24.2
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; fi && \
    if [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi && \
    echo $ARCH && \
    curl --location https://golang.org/dl/go1.24.2.linux-${ARCH}.tar.gz | tar xz -C /usr/local # legit:ignore-pipeline
ENV PATH=/usr/local/go/bin:$PATH

WORKDIR /app

COPY . /app

RUN set -e && go mod tidy && go test ./pkg/services/http/ -v && go build  -ldflags "-X main.buildVersion=${BUILD_VERSION}" -o api-layer main.go

FROM ubuntu:22.04 AS api-layer-release

ARG TEST=false
ENV TEST=${TEST}

RUN addgroup --system appuser && \
  adduser --system --group appuser

RUN apt-get update && \
  apt-get -y upgrade && \
  apt-get install -yq curl ca-certificates

RUN rm -rf /var/cache/apt/archives /var/lib/apt/lists/*

# Setup the production user
RUN addgroup --system prod && adduser --system --ingroup prod prod
RUN mkdir /var/prod && \
    chown -R prod:prod /var/prod

# Copy only the built binary from the build stage
COPY --from=build --chown=prod:prod /app/api-layer /var/prod

WORKDIR /var/prod
USER prod

ENTRYPOINT [ "sh", "-c", "./api-layer \
            -port=\"${PORT}\" \
            -test=\"${TEST}\" \
            -allowOrigins=\"${ALLOW_ORIGINS}\" \
            -clickhouseUrl=\"${CLICKHOUSE_URL}\" \
            -clickhouseUser=\"${CLICKHOUSE_USER}\" \
            -clickhouseDB=\"${CLICKHOUSE_DB}\" \
            -clickhousePass=\"${CLICKHOUSE_PASS}\" \
            -clickhousePort=\"${CLICKHOUSE_PORT}\" \
            -baseUrl=\"${BASE_URL}\" \
            "]
