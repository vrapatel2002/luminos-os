#!/bin/bash
# Quick OpenRouter key + DeepSeek V4 Pro test
# Reads key from .env, tests auth and inference
KEY=$(grep '^OPENROUTER_API_KEY=' /home/shawn/luminos-os/.env | cut -d'=' -f2)
echo "Key prefix: ${KEY:0:8}..."
echo "Key length: ${#KEY}"
echo "---"
echo "Testing auth..."
curl -s https://openrouter.ai/api/v1/auth/key -H "Authorization: Bearer $KEY"
echo ""
echo "---"
echo "Testing DeepSeek V4 Pro inference..."
curl -s https://openrouter.ai/api/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"deepseek/deepseek-v4-pro","max_tokens":30,"messages":[{"role":"user","content":"Say hi and name yourself in 5 words"}]}'
echo ""
echo "---"
echo "Done."
