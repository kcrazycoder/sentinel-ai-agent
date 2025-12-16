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
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE_NAME" .

if [ $? -ne 0 ]; then
    echo "Build failed! Aborting."
    exit 1
fi

# Deploy
echo "Deploying to Cloud Run..."
# Note: We are using allow-unauthenticated for the Hackathon "public url" requirement.
# Change to --no-allow-unauthenticated for private services.

gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/$PROJECT_ID/$SERVICE_NAME" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "DD_LLMOBS_ENABLED=1,DD_LLMOBS_ML_APP=sentinel-ai-agent,$(grep -v '^#' .env | grep -v 'GOOGLE_APPLICATION_CREDENTIALS' | tr '\n' ',' | sed 's/,$//')"

# Note on Credentials:
# Cloud Run uses the Default Service Account by default.
# It does NOT need GOOGLE_APPLICATION_CREDENTIALS for Vertex AI if that SA has permissions.
# Ensure your Compute Engine default service account has "Vertex AI User" role.

echo "================================================="
echo "Deployment Complete!"
echo "================================================="
