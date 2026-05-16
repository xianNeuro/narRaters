#!/bin/bash
# Interactive script to set up API keys for Anthropic (Claude) and OpenAI (GPT)

echo "=========================================="
echo "API Key Setup for narRater"
echo "=========================================="
echo ""

setup_key() {
    local provider_name="$1"
    local env_var="$2"
    local console_url="$3"

    echo "--- $provider_name ---"
    current_val="${!env_var}"
    if [ -n "$current_val" ]; then
        echo "✓ $env_var is already set (length: ${#current_val})"
        echo ""
        return
    fi

    echo "$env_var is not set."
    read -p "Set $provider_name key permanently in ~/.zshrc? (y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your $provider_name API key: " api_key
        if [ -n "$api_key" ]; then
            if ! grep -q "$env_var" ~/.zshrc 2>/dev/null; then
                echo "" >> ~/.zshrc
                echo "# $provider_name API Key for narrative processor" >> ~/.zshrc
                echo "export $env_var='$api_key'" >> ~/.zshrc
                echo "✓ $env_var added to ~/.zshrc"
                echo "  Run 'source ~/.zshrc' or open a new terminal to use it"
            else
                echo "⚠ $env_var already exists in ~/.zshrc — edit ~/.zshrc manually to update"
            fi
        else
            echo "✗ No key provided, skipping"
        fi
    else
        echo "To set manually: export $env_var='your-key-here'"
        echo "Get your key from: $console_url"
    fi
    echo ""
}

setup_key "Anthropic (Claude)" "ANTHROPIC_API_KEY" "https://console.anthropic.com/"
setup_key "OpenAI (GPT)" "OPENAI_API_KEY" "https://platform.openai.com/api-keys"

echo "=========================================="
echo "Done. See developer/SETUP_API.md for more details."
echo "=========================================="
