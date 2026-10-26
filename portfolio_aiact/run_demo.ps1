# Builds the AI Act corpus and asks the three demo questions.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File portfolio_aiact\run_demo.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

# Provider settings (LLM_PROVIDER, GENERATION_MODEL, keys) come from .env
if (Test-Path .env) {
  Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
      [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
    }
  }
}
# ...but never the database from .env: this demo has its own.
$env:DATABASE_URL = "postgresql://secrag:secrag@localhost:5435/secrag_aiact"
if ($env:LLM_PROVIDER -eq "echo" -or -not $env:LLM_PROVIDER) {
  Write-Warning "LLM_PROVIDER is echo: every answer will be INSUFFICIENT_CONTEXT. Set it to anthropic or vertex in .env."
}

$py = if (Test-Path .venv\Scripts\python.exe) { ".venv\Scripts\python.exe" } else { "python" }

docker compose -f portfolio_aiact/docker-compose.yml down -v
docker compose -f portfolio_aiact/docker-compose.yml up -d --wait
& $py portfolio_aiact/build_corpus.py
& $py demo/load_demo.py --corpus portfolio_aiact/aiact_corpus.json --database-url $env:DATABASE_URL
& $py portfolio_aiact/ask.py
