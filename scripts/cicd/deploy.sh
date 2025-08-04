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

fix_remote_permissions() {
  echo ">>> [Deploy] Fixing remote permissions..."
  ssh -o "ControlPath=$SSH_SOCKET" "$REMOTE_HOST" << 'REMOTE'
    sudo chown -R root:docker /opt/xrouter-mcp-marketplace
    sudo chmod -R 770 /opt/xrouter-mcp-marketplace
REMOTE
}

setup_ssh_connection() {
  local ssh_key_path="$1"
  local remote_host="$2"

  # Setup SSH connection multiplexing to avoid multiple password prompts
  local ssh_socket="/tmp/ssh-deploy-$$"

  echo ">>> [Deploy] Setting up SSH connection..."
  ssh -i "$ssh_key_path" -M -S "$ssh_socket" -fN "$remote_host"

  # Export for use in other functions
  export SSH_SOCKET="$ssh_socket"
  export SSH_KEY_PATH="$ssh_key_path"
  export REMOTE_HOST="$remote_host"
}

cleanup_ssh_connection() {
  if [[ -n "${SSH_SOCKET:-}" ]]; then
    echo ">>> [Deploy] Cleaning up SSH connection..."
    ssh -S "$SSH_SOCKET" -O exit "$REMOTE_HOST" 2>/dev/null || true
  fi
}

copy_deployment_files() {
  echo ">>> [Deploy] Copying deployment files..."

  # Copy all files using the shared SSH connection
  scp -o "ControlPath=$SSH_SOCKET" \
    docker-compose.prod.yml .env.prod \
    "$REMOTE_HOST:/opt/xrouter-mcp-marketplace/"

  scp -o "ControlPath=$SSH_SOCKET" \
    mcp-xrouter-marketplace/docker-compose.prod.yml mcp-xrouter-marketplace/.env.prod \
    "$REMOTE_HOST:/opt/xrouter-mcp-marketplace/mcp-server/"

}

deploy_component() {
  local component_name="$1"
  local compose_file="$2"
  local env_file="$3"

  echo ">>> [Deploy] Processing $component_name..."

  # Load environment and pull
  set -a
  source "$env_file"
  set +a
  docker compose -f "$compose_file" pull

  # Stop and start
  docker compose -f "$compose_file" down
  docker compose -f "$compose_file" up -d
}

deploy_remote() {
  local docker_token="$1"
  local docker_username="$2"

  echo ">>> [Deploy] Executing remote deployment..."
  ssh -t -t -o "ControlPath=$SSH_SOCKET" "$REMOTE_HOST" << EOF
    cd /opt/xrouter-mcp-marketplace

    # Load main environment variables
    set -a
    source .env.prod
    set +a

    # Login to Github Container Registry
    echo ">>> [Deploy] Logging in to GHCR..."
    echo "$docker_token" | docker login ghcr.io --username "$docker_username" --password-stdin

    # Define deployment function
    deploy_component() {
      local component_name="\$1"
      local compose_file="\$2"
      local env_file="\$3"

      echo ">>> [Deploy] Processing \$component_name..."

      # Load environment and pull
      set -a
      source "\$env_file"
      set +a
      docker compose -f "\$compose_file" pull

      # Stop and start
      docker compose -f "\$compose_file" down
      docker compose -f "\$compose_file" up -d
    }

    # Deploy all components
    deploy_component "Root" "docker-compose.prod.yml" ".env.prod"
    deploy_component "MCP Server" "mcp-server/docker-compose.prod.yml" "mcp-server/.env.prod"

    # Logout from registry
    echo ">>> [Deploy] Logging out from GHCR..."
    docker logout ghcr.io

    # Set final permissions
    echo ">>> [Deploy] Setting final permissions..."
    sudo chown -R root:docker /opt/xrouter-mcp-marketplace
    sudo chmod -R 660 /opt/xrouter-mcp-marketplace
    sudo find /opt/xrouter-mcp-marketplace -type d -exec chmod 770 {} \;

    # Show running containers
    echo ">>> [Deploy] Current running containers:"
    docker ps
EOF
}

main() {
  echo ">>> [Deploy] Starting deployment process..."

  # Setup cleanup trap
  trap cleanup_ssh_connection EXIT

  # Load environment variables
  load_env ".env"

  # Read secrets
  local remote_host
  local ssh_key_path
  local docker_token
  local docker_username

  remote_host=$(read_first_line_of_file "secrets/.ssh-host")
  ssh_key_path=$(read_first_line_of_file "secrets/.ssh-privkey-path")
  docker_token=$(read_first_line_of_file "secrets/.docker-oauth-token")
  docker_username=$(read_first_line_of_file "secrets/.docker-login-username")

  echo ">>> [Deploy] Deploying to $remote_host..."

  # Setup SSH connection multiplexing (only one password prompt!)
  setup_ssh_connection "$ssh_key_path" "$remote_host"

  # Execute deployment steps using shared SSH connection
  fix_remote_permissions
  copy_deployment_files
  deploy_remote "$docker_token" "$docker_username"

  echo ">>> [Deploy] Deployment completed successfully!"
}

main
