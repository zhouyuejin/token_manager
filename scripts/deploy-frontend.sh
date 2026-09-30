#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <ssh-user@host|ssh-alias>" >&2
  exit 2
fi

target=$1
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
remote_dist=/opt/token-manager/frontend/dist

command -v rsync >/dev/null || {
  echo "rsync is missing on this computer." >&2
  exit 1
}

ssh "$target" 'test -d /opt/token-manager/frontend && command -v rsync >/dev/null' || {
  echo "Cannot reach the ECS project directory, or rsync is missing on the ECS." >&2
  exit 1
}

(
  cd "$repo_dir/frontend"
  # The unused @ant-design/x package currently declares an antd 6 peer.
  npm ci --legacy-peer-deps
  npm run build
)

ssh "$target" "mkdir -p '$remote_dist'"
rsync -az --delete -- "$repo_dir/frontend/dist/" "$target:$remote_dist/"
ssh "$target" "test -s '$remote_dist/index.html'"
echo "Frontend deployed to $target:$remote_dist"
