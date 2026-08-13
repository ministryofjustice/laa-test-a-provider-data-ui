#!/usr/bin/env bash
set -euo pipefail

# Restart the local Docker app stack wired to a local PDA-R2 backend.
export PDA_USE_MOCK_API=false
# IMPORTANT: inside Docker, localhost refers to the container itself.
# Use host.docker.internal to reach a backend running on your Mac host.
export PDA_URL="${PDA_URL:-http://host.docker.internal:8080}"
export PDA_API_KEY="Dummy1"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://localhost:8080/swagger-ui/index.html}"

echo "Stopping existing containers..."
docker compose down --remove-orphans

echo "Starting containers with PDA-R2 config..."
docker compose up --build -d

echo "Done. Running services:"
docker compose ps

echo ""
echo "PDA configuration:"
echo "  PDA_USE_MOCK_API=${PDA_USE_MOCK_API}"
echo "  PDA_URL=${PDA_URL}"
echo "  PDA_API_KEY=${PDA_API_KEY}"

echo ""
echo "Checking backend from host..."
if curl -fsS "${BACKEND_HEALTH_URL}" >/dev/null; then
	echo "Backend reachable from host: ${BACKEND_HEALTH_URL}"
else
	echo "Warning: backend not reachable from host at ${BACKEND_HEALTH_URL}."
	echo "Ensure your PDA-R2 backend is running and accessible from Docker."
fi
