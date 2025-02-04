#!/usr/bin/bash

# Set download URL for the latest Chromium build
LATEST_URL="https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2FLAST_CHANGE?alt=media"

# Fetch the latest build number
LATEST_BUILD=$(curl -s $LATEST_URL)

# Define the installation directory
INSTALL_DIR="/usr/lib/chromium"
mkdir -p "$INSTALL_DIR"

# Download the latest Chromium build
echo "Downloading the latest Chrome build ($LATEST_BUILD)..."
curl -Lo "$INSTALL_DIR/chrome-linux.zip" "https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F$LATEST_BUILD%2Fchrome-linux.zip?alt=media"

# Extract and move to installation directory
unzip -q "$INSTALL_DIR/chrome-linux.zip" -d "$INSTALL_DIR/"
mv "$INSTALL_DIR/chrome-linux"/* "$INSTALL_DIR/"
rm -rf "$INSTALL_DIR/chrome-linux" "$INSTALL_DIR/chrome-linux.zip"

# Make chromium executable and create symlink
chmod +x "$INSTALL_DIR/chrome"
ln -sf "$INSTALL_DIR/chrome" /usr/bin/chromium

echo "Chrome installed successfully at $INSTALL_DIR"