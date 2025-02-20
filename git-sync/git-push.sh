#!/bin/sh

cd /app/data || exit 1

# Ensure Git is initialized and the correct remote is set
if [ ! -d ".git" ]; then
  echo "No Git repository found. Cloning the repository..."
  git clone --branch "$GIT_BRANCH" "$GIT_REPO" /tmp/repo || {
    echo "Failed to clone repository!"
    exit 1
  }
  mv /tmp/repo/.git /app/data/  # Move Git repo to /data
  rm -rf /tmp/repo
fi

# Move into the repo (should be inside /data/)
cd /app/data || exit 1

# Ensure we are on the correct branch
git checkout "$GIT_BRANCH"

# Add only the files inside /data to the 'data/' folder in the repository
git add -A

# Check for changes before committing
if git diff-index --quiet HEAD --; then
  echo "No changes to commit."
else
  git pull
  git commit -m "Automated sync of sensor data"
  git push origin "$GIT_BRANCH"
  echo "Successfully pushed data to remote repository."
fi