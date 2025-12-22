#!/bin/bash

# Configuration
SERVICE_NAME="sentinel-ai"
REGION="us-central1"

# Load Project ID from .env if possible, otherwise ask
if [ -f .env ]; then
  # Try to extract project_id from .env handling quotes/spaces
  PROJECT_ID=$(grep -v '^#' .env | grep -i 'project_id' | cut -d '=' -f2 | tr -d '"' | tr -d "'" | tr -d '\r')
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Enter your Google Cloud Project ID:"
  read PROJECT_ID
fi

echo "================================================="
echo "Deploying $SERVICE_NAME to Google Cloud Run"
echo "Project ID: $PROJECT_ID"
echo "Region:     $REGION"
echo "================================================="

# Check for gcloud
if ! command -v gcloud &> /dev/null; then
  echo "Error: gcloud CLI is not installed or not in PATH."
  echo "Please install the Google Cloud SDK and try again."
  exit 1
fi

# Set project
echo "Setting active project..."
gcloud config set project "$PROJECT_ID"

# Enable services if needed (optional check)
# gcloud services enable run.googleapis.com cloudbuild.googleapis.com

# Submit Build
echo "Submitting build to Cloud Build..."
TIMESTAMP=$(date +%s)
IMAGE_TAG="gcr.io/$PROJECT_ID/$SERVICE_NAME:$TIMESTAMP"
gcloud builds submit --tag "$IMAGE_TAG" .

if [ $? -ne 0 ]; then
    echo "Build failed! Aborting."
    exit 1
fi

# Deploy
# Generate service.yaml
echo "Generating service.yaml from template..."

# Load APM vars or defaults
export DD_SERVICE=${SERVICE_NAME}
export DD_ENV=${DD_ENV:-production}
export DD_VERSION=${DD_VERSION:-1.0.0}
export DD_VERSION_LABEL=$(echo "$DD_VERSION" | tr '.' '-')
export DD_LOGS_INJECTION="true"
export DD_LLMOBS_ENABLED=${DD_LLMOBS_ENABLED:-1}
export DD_LLMOBS_ML_APP=${DD_LLMOBS_ML_APP:-${SERVICE_NAME}}
export IMAGE_URL="$IMAGE_TAG"
export PROJECT_ID=$PROJECT_ID
export SERVICE_NAME=$SERVICE_NAME

# Load keys from .env
if [ -f .env ]; then
  # Sourcing .env is risky if it has comments/spaces, but typical for simple envs.
  # Better: Read key-by-key for known keys.
  export DD_API_KEY=$(grep -v '^#' .env | grep 'DD_API_KEY' | cut -d '=' -f2 | tr -d '"' | tr -d "'")
  export ELEVENLABS_API_KEY=$(grep -v '^#' .env | grep 'ELEVENLABS_API_KEY' | cut -d '=' -f2 | tr -d '"' | tr -d "'")
  export DD_SITE=$(grep -v '^#' .env | grep 'DD_SITE' | cut -d '=' -f2 | tr -d '"' | tr -d "'")
  
  # Format remaining env vars as YAML list items for the APP container
  # Excluding the ones we already handled explicitly
  APP_ENV_VARS_BLOCK=""
  while IFS='=' read -r key value; do
    if [[ $key =~ ^#.* ]] || [[ -z $key ]]; then continue; fi
    # Skip items we handled or don't want (Credentials handled by Identity)
    if [[ "$key" == "GOOGLE_APPLICATION_CREDENTIALS" ]] || \
       [[ "$key" == "DD_API_KEY" ]] || [[ "$key" == "DD_SITE" ]] || \
       [[ "$key" == "project_id" ]] || [[ "$key" == "DD_SERVICE" ]] || \
       [[ "$key" == "DD_ENV" ]] || [[ "$key" == "DD_VERSION" ]] || \
       [[ "$key" == "DD_LOGS_INJECTION" ]] || [[ "$key" == "DD_LLMOBS_ENABLED" ]] || \
       [[ "$key" == "DD_LLMOBS_ML_APP" ]] || [[ "$key" == "DD_APP_KEY" ]] || \
       [[ "$key" == "ELEVENLABS_API_KEY" ]]; then
       continue
    fi
    # Clean value
    val=$(echo "$value" | tr -d '"' | tr -d "'")
    APP_ENV_VARS_BLOCK="${APP_ENV_VARS_BLOCK}$(printf "\n        - name: %s\n          value: \"%s\"" "$key" "$val")"
  done < .env
  export APP_ENV_VARS_BLOCK
fi


# Use envsubst to replace variables in template
# We need strictly the variables we defined to be replaced, to avoid accidental replacement if user has $ in file
# But simple envsubst is usually fine for this template.
envsubst < service.yaml.template > service.yaml

# Deploy
echo "Deploying to Cloud Run using service.yaml..."
gcloud run services replace service.yaml --region "$REGION"

# Allow unauthenticated (since 'replace' might reset permissions or strict default)
gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker"

# Note on Credentials:
# Cloud Run uses the Default Service Account by default.
# It does NOT need GOOGLE_APPLICATION_CREDENTIALS for Vertex AI if that SA has permissions.
# Ensure your Compute Engine default service account has "Vertex AI User" role.

echo "================================================="
echo "Deployment Complete!"
echo "================================================="
