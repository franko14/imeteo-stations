#!/bin/bash

# Build the Docker image
docker build -t imeteo-stations .

echo "Docker image built successfully!"
echo ""
echo "Usage examples:"
echo "  docker run --rm imeteo-stations --help"
echo "  docker run --rm imeteo-stations fetch --station-id 11816"
echo "  docker run --rm imeteo-stations search --query Bratislava"
echo "  docker run --rm imeteo-stations list-stations"