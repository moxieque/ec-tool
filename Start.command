#!/bin/bash
# ============================================================
#  EC Sales Management Tool
#  Start script for macOS
# ============================================================

# Move to the folder where this script is located
cd "$(dirname "$0")" || exit 1

echo "================================================"
echo "  EC Sales Management Tool"
echo "================================================"
echo ""

# ─────────────────────────────────────────
# 1. Check Python3
# ─────────────────────────────────────────
echo "▶ Checking Python3..."
if ! command -v python3 &>/dev/null; then
  echo ""
  echo "  Python3 not found. Downloading installer..."
  echo "  (Internet connection required. Please wait...)"
  echo ""

  # Get latest macOS Python installer
  PYTHON_PKG_URL=$(curl -sL https://www.python.org/downloads/ \
    | grep -o 'https://www.python.org/ftp/python/[^"]*macos11\.pkg' \
    | head -1)

  if [ -z "$PYTHON_PKG_URL" ]; then
    # Fallback to specific stable version
    PYTHON_PKG_URL="https://www.python.org/ftp/python/3.13.2/python-3.13.2-macos11.pkg"
  fi

  INSTALLER_PATH="/tmp/python_installer.pkg"
  echo "  Downloading: $PYTHON_PKG_URL"
  curl -L --progress-bar -o "$INSTALLER_PATH" "$PYTHON_PKG_URL"

  if [ $? -ne 0 ] || [ ! -f "$INSTALLER_PATH" ]; then
    echo ""
    echo "【Error】Download failed."
    echo "Please check your internet connection and try again."
    read -p "Press Enter to close..."
    exit 1
  fi

  echo ""
  echo "  Opening installer..."
  echo "  ─────────────────────────────────────────"
  echo "  Follow the installation steps:"
  echo "    「Continue」→「Continue」→「Agree」→「Install」"
  echo "  ─────────────────────────────────────────"
  echo ""
  echo "  ✅ After installation completes,"
  echo "     close this window and double-click Start.command again."
  echo ""

  open "$INSTALLER_PATH"
  read -p "(Press Enter after installation is complete)"

  # Verify installation
  if ! command -v python3 &>/dev/null; then
    echo ""
    echo "【Error】Python3 still not found."
    echo "Please verify installation and try again."
    read -p "Press Enter to close..."
    exit 1
  fi

  echo "  OK: Python3 installation confirmed. Continuing..."
  echo ""
fi

PYTHON_VER=$(python3 --version 2>&1)
echo "  OK: $PYTHON_VER"
echo ""

# ─────────────────────────────────────────
# 2. Check and install required libraries
# ─────────────────────────────────────────
echo "▶ Checking required libraries..."

NEED_INSTALL=0
python3 -c "import flask" 2>/dev/null        || NEED_INSTALL=1
python3 -c "import flask_cors" 2>/dev/null   || NEED_INSTALL=1
python3 -c "import playwright" 2>/dev/null   || NEED_INSTALL=1

if [ "$NEED_INSTALL" -eq 1 ]; then
  echo "  Installing libraries (first time only, may take a few minutes)..."
  echo ""
  pip3 install flask flask-cors playwright --quiet --disable-pip-version-check
  if [ $? -ne 0 ]; then
    echo ""
    echo "【Error】Library installation failed."
    echo "Please check your internet connection."
    read -p "Press Enter to close..."
    exit 1
  fi
  echo "  OK: Libraries installed"
else
  echo "  OK: Libraries already installed"
fi
echo ""

# ─────────────────────────────────────────
# 3. Install Playwright browser (if needed)
# ─────────────────────────────────────────
PLAYWRIGHT_DIR="$HOME/Library/Caches/ms-playwright"
if [ ! -d "$PLAYWRIGHT_DIR" ] || [ -z "$(ls -A "$PLAYWRIGHT_DIR" 2>/dev/null)" ]; then
  echo "▶ Installing browser component (first time only)..."
  python3 -m playwright install chromium --quiet
  if [ $? -ne 0 ]; then
    echo ""
    echo "【Warning】Browser installation failed."
    echo "Rakumart auto-import may not work."
    echo ""
  else
    echo "  OK: Browser installed"
    echo ""
  fi
fi

# ─────────────────────────────────────────
# 4. Start server and open browser
# ─────────────────────────────────────────
echo "▶ Starting server..."
echo ""

# Open browser after 3 seconds (wait for server startup)
(sleep 3 && open "http://localhost:8080") &

python3 app.py

# Show message when server stops
echo ""
echo "================================================"
echo "  Server stopped."
echo "  You can close this window."
echo "================================================"
read -p ""
