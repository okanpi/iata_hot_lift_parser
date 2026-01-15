#!/bin/bash
# IATA HOT/LIFT Parser - Google Cloud Run Deploy Script
# Project: iata-hot-lift

set -e

PROJECT_ID="iata-hot-lift"
SERVICE_NAME="iata-hot-parser"
REGION="europe-west1"

echo "=========================================="
echo "IATA HOT/LIFT Parser - Cloud Run Deploy"
echo "=========================================="
echo ""

# Set project
echo "[1/4] Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable APIs
echo "[2/4] Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com --quiet

# Build and push image
echo "[3/4] Building container image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME --quiet

# Deploy to Cloud Run
echo "[4/4] Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --quiet

echo ""
echo "=========================================="
echo "Deploy completed!"
echo "=========================================="

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo ""
echo "Your application is live at:"
echo "$SERVICE_URL"
echo ""
