#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICES_DIR="$PROJECT_DIR/services"

mkdir -p "$SERVICES_DIR"

repositories=(
  "calculadora-rtc-regime-regular"
  "calculadora-rtc-simples-nacional"
  "calculadora-rtc-gerador-danfse"
)

for repository in "${repositories[@]}"; do
  destination="$SERVICES_DIR/$repository"
  if [[ -d "$destination/.git" ]]; then
    echo "Já existe: $destination"
  else
    git clone "https://github.com/ReceitaFederal/$repository.git" "$destination"
  fi
done
