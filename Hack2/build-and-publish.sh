#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Run electron-builder with publish
npx electron-builder --publish=always
