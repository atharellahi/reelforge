#!/usr/bin/env bash
# reelforge one-line installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/atharellahi/reelforge/main/install.sh | bash
#
# Installs what is missing (Python, git, ffmpeg, Chrome), then reelforge and its
# Claude Code skill. Safe to run again. Keys are NOT asked for here - put them
# in ~/.reelforge/.env or <repo>/.reelforge/.env, or let Claude ask you.
set -euo pipefail
REPO="${REELFORGE_REPO:-https://github.com/atharellahi/reelforge.git}"
step() { printf '\n\033[36m==> %s\033[0m\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

if [[ "$(uname -s)" == "Darwin" ]]; then
  if ! have brew; then
    step "Installing Homebrew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
  fi
  for pkg in python git ffmpeg pipx; do have "${pkg/python/python3}" || { step "Installing $pkg"; brew install "$pkg"; }; done
  have pipx || brew install pipx
  if [[ ! -d "/Applications/Google Chrome.app" && ! -d "/Applications/Chromium.app" && ! -d "/Applications/Microsoft Edge.app" ]]; then
    step "Installing Google Chrome"; brew install --cask google-chrome
  fi
else
  if have apt-get; then
    step "Installing system packages (sudo)"
    sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv git ffmpeg pipx
    if ! have google-chrome && ! have chromium && ! have chromium-browser; then
      sudo apt-get install -y -qq chromium-browser 2>/dev/null || sudo apt-get install -y -qq chromium
    fi
  else
    echo "Install python3, git, ffmpeg, pipx and Chrome/Chromium with your package manager, then re-run."; exit 1
  fi
fi

step "Installing reelforge from $REPO"
pipx ensurepath >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"
pipx install --force "git+$REPO" >/dev/null
pipx inject reelforge faster-whisper >/dev/null 2>&1 || echo "  (faster-whisper skipped - optional)"

step "Installing the Claude Code skill"
reelforge skill install

step "Checking the machine"
reelforge doctor

ENVF="$HOME/.reelforge/.env"
if [[ ! -f "$ENVF" ]]; then
  cat > "$ENVF" <<'EOF'
# reelforge keys - this file is yours, never committed.
# Required:
GEMINI_API_KEY=
# Optional (publishing):
YOUTUBE_CLIENT_SECRET=
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_USER_ID=
# Optional (live-action hook plates, billed per second):
VEO_API_KEY=
VEO_PROJECT=
EOF
fi

printf '\n\033[32mDone.\033[0m\n'
echo "  1. Put your Gemini key in: $ENVF"
echo "  2. Open a NEW terminal, cd into your project, run: claude"
echo "  3. Say: make a 30-second short about <a feature>   (or: open the reelforge ui)"
