#!/usr/bin/env bash
#
# Build and publish the web app to Firebase Hosting.
#
#   cd ~/sample && git pull && bash deploy.sh
#
# Deliberately does NOT pull: bash reads a script as it runs, so a script that
# rewrites itself mid-run can misbehave. Pull first, then call this.
#
# Runs npm install every time — cheap when nothing changed, and it is what keeps
# a newly added dependency from failing the build after a pull.

set -euo pipefail

cd "$(dirname "$0")"
PROJECT="${FIREBASE_PROJECT:-table-93579}"

echo "==> Installing dependencies"
cd ui_react_tailwind
npm install --no-audit --no-fund

echo "==> Running tests"
npm test

echo "==> Building"
npm run build
cd ..

echo "==> Deploying to Firebase ($PROJECT)"
npx firebase-tools deploy --only hosting,firestore --project "$PROJECT"

echo "==> Done: https://${PROJECT}.web.app"
