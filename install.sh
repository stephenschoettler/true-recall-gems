#!/bin/bash
set -e

INSTALL_DIR="$HOME/.openclaw/true-recall-gems"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo ""
echo "========================================"
echo "  TrueRecall Gems + Blocks Installer"
echo "========================================"
echo ""

# Interactive config
read -p "Qdrant host:port [localhost:6333]: " QDRANT_HOST
QDRANT_HOST=${QDRANT_HOST:-localhost:6333}

read -p "Ollama host:port [localhost:11434]: " OLLAMA_HOST
OLLAMA_HOST=${OLLAMA_HOST:-localhost:11434}

read -p "Groq API key: " GROQ_KEY
if [ -z "$GROQ_KEY" ]; then
    echo "ERROR: Groq API key is required."
    exit 1
fi

read -p "User ID [user]: " USER_ID
USER_ID=${USER_ID:-user}

echo ""
echo "Configuration:"
echo "  Qdrant:   http://$QDRANT_HOST"
echo "  Ollama:   http://$OLLAMA_HOST"
echo "  User ID:  $USER_ID"
read -p "Proceed? [Y/n]: " CONFIRM
CONFIRM=${CONFIRM:-Y}
if [[ "$CONFIRM" != [Yy]* ]]; then
    echo "Aborted."
    exit 0
fi

# Write env file
cat > "$INSTALL_DIR/gems.env" << ENV
QDRANT_URL=http://$QDRANT_HOST
OLLAMA_URL=http://$OLLAMA_HOST
GROQ_API_KEY=$GROQ_KEY
EMBEDDING_MODEL=snowflake-arctic-embed2
USER_ID=$USER_ID
ENV
echo "✓ Wrote $INSTALL_DIR/gems.env"

# Create Qdrant collections
echo "Creating Qdrant collections..."
curl -sf -X PUT "http://$QDRANT_HOST/collections/gems_tr" \
    -H "Content-Type: application/json" \
    -d '{"vectors":{"size":1024,"distance":"Cosine"}}' > /dev/null && echo "✓ gems_tr collection ready" || echo "  gems_tr may already exist"

curl -sf -X PUT "http://$QDRANT_HOST/collections/topic_blocks_tr" \
    -H "Content-Type: application/json" \
    -d '{"vectors":{"size":1024,"distance":"Cosine"}}' > /dev/null && echo "✓ topic_blocks_tr collection ready" || echo "  topic_blocks_tr may already exist"

# Install systemd files
mkdir -p "$SYSTEMD_DIR"
cp "$INSTALL_DIR/systemd/"*.service "$SYSTEMD_DIR/"
cp "$INSTALL_DIR/systemd/"*.timer "$SYSTEMD_DIR/"
echo "✓ Installed systemd service and timer files"

systemctl --user daemon-reload
systemctl --user enable --now gems-curator.timer
systemctl --user enable --now blocks-curator.timer
echo "✓ Timers enabled and started"

# Run gems curator once to verify
echo ""
echo "Running gems curator once to verify..."
source "$INSTALL_DIR/gems.env"
export QDRANT_URL OLLAMA_URL GROQ_API_KEY EMBEDDING_MODEL USER_ID
python3 "$INSTALL_DIR/curator/gems_curator.py" 2>&1 | tail -10

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
systemctl --user status gems-curator.timer --no-pager | grep -E "Active|Trigger"
systemctl --user status blocks-curator.timer --no-pager | grep -E "Active|Trigger"
echo ""
echo "Search gems:  python3 $INSTALL_DIR/scripts/search_gems.py 'your query'"
echo "Search blocks: python3 $INSTALL_DIR/scripts/search_blocks.py 'your query'"
