# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0


# Documentation available at: https://docs.docker.com/build/bake/

# Docker build args
variable "IMAGE_REPO" { default = "" }
variable "IMAGE_TAG" { default = "v0.0.0-dev" }

function "get_tag" {
  params = [tags, name]
  // Check if IMAGE_REPO ends with name to avoid repetition
  result = [for tag in tags:
    can(regex("${name}$", IMAGE_REPO)) ?
      "${IMAGE_REPO}:${tag}" :
      "${IMAGE_REPO}/${name}:${tag}"
  ]
}

group "default" {
  targets = [
    "slim",
  ]
}

group "data-plane" {
  targets = [
    "slim",
  ]
}

target "_common" {
  output = [
    "type=image",
  ]
  platforms = [
    "linux/arm64",
    "linux/amd64",
  ]
}

target "docker-metadata-action" {
  tags = []
}


target "api" {
  context = "./api-layer"
  dockerfile = "./Dockerfile"
  target = "api-layer-release"
  inherits = [
    "_common",
    "docker-metadata-action",
  ]
  tags = get_tag(target.docker-metadata-action.tags, "${target.api.name}")
}

target "api-debug" {
  context = "./api-layer"
  dockerfile = "./Dockerfile"
  target = "api-layer-debug"
  inherits = [
    "_common",
    "docker-metadata-action",
  ]
  tags = get_tag(target.docker-metadata-action.tags, "${target.api-debug.name}")
}

target "mce" {
  context = "./metrics_computation_engine"
  dockerfile = "./Dockerfile"
  target = "mce-release"
  inherits = [
    "_common",
    "docker-metadata-action",
  ]
  tags = get_tag(target.docker-metadata-action.tags, "${target.mce.name}")
}

target "mce-debug" {
  context = "./metrics_computation_engine"
  dockerfile = "./Dockerfile"
  target = "mce-debug"
  inherits = [
    "_common",
    "docker-metadata-action",
  ]
  tags = get_tag(target.docker-metadata-action.tags, "${target.mce-debug.name}")
}
