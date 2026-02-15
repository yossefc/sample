#!/usr/bin/env bash
# ============================================================
#  Deploy Luach Mivchanim to Firebase Hosting + Cloud Run
# ============================================================
#
#  Prerequisites:
#    1. gcloud CLI installed
#    2. firebase CLI installed: npm install -g firebase-tools
#    3. Docker (or use gcloud builds submit)
#    4. Logged in: gcloud auth login && firebase login
#    5. .firebaserc has your project ID
#
#  Usage:  chmod +x deploy.sh && ./deploy.sh
# ============================================================

set -e

PROJECT_ID="table-93579"
REGION="me-west1"
SERVICE_NAME="luach-mivchanim"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo ""
echo "[1/5] Setting gcloud project..."
gcloud config set project "$PROJECT_ID"

echo ""
echo "[2/5] Building Docker image via Cloud Build..."
gcloud builds submit --tag "$IMAGE" .

echo ""
echo "[3/5] Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 512Mi \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"

echo ""
echo "[4/5] Getting Cloud Run URL..."
CLOUD_RUN_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" --format "value(status.url)")
echo "   Cloud Run URL: $CLOUD_RUN_URL"

echo ""
echo "[5/5] Deploying Firebase Hosting..."
firebase deploy --only hosting

echo ""
echo "============================================================"
echo " DEPLOY COMPLETE"
echo "============================================================"
echo " Cloud Run:        $CLOUD_RUN_URL"
echo " Firebase Hosting: https://${PROJECT_ID}.web.app"
echo ""
echo " Public link for parents:"
echo " https://${PROJECT_ID}.web.app/?school_id=MON-ECOLE&class=YA&mode=view"
echo "============================================================"
