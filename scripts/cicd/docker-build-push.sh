#!/bin/bash

set -euo pipefail

read_first_line_of_file() {
  local file="$1"
  if [[ -e "$file" ]]; then
    read -r line < "$file"
    echo "$line"
  else
    echo "File $file does not exist." >&2
    exit 1
  fi
}

load_env() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    set -a
    source "$env_file"
    set +a
  else
    echo "Environment file $env_file not found." >&2
    exit 1
  fi
}

build_and_push() {
  local project_name="$1"
  local build_compose="$2"
  local dev_compose="$3"
  local env_file="$4"
  local stop_and_up_dev="${5:-true}"

  echo ">>> [$project_name] Loading env from $env_file"
  load_env "$env_file"

  echo ">>> [$project_name] Building Docker image..."
  docker compose -f "$build_compose" build

  echo ">>> [$project_name] Build successful."

  if [[ "$stop_and_up_dev" == "true" ]]; then
    echo ">>> [$project_name] Restarting dev containers..."
    docker compose -f "$dev_compose" down
    docker compose -f "$dev_compose" up -d
  fi

  echo ">>> [$project_name] Logging in to GHCR..."
  echo "$docker_token" | docker login ghcr.io --username "$docker_username" --password-stdin

  echo ">>> [$project_name] Pushing image..."
  docker compose -f "$build_compose" push

  echo ">>> [$project_name] Logging out from GHCR..."
  docker logout ghcr.io

  echo ">>> [$project_name] Build and push completed."
}

main() {
  docker_token=$(read_first_line_of_file "secrets/.docker-oauth-token")
  docker_username=$(read_first_line_of_file "secrets/.docker-login-username")

  build_and_push "Root" \
    "docker-compose.build.yml" \
    "docker-compose.dev.yml" \
    ".env"

}

main
