# Load .env into the current PowerShell session.
#
#   . .\load-env.ps1
#
# The leading dot matters: it runs the script in the current session rather than
# a child process, which is the only way the variables survive the call.

if (-not (Test-Path .env)) {
    Write-Host "No .env found. Copy .env.example to .env and fill it in." -ForegroundColor Yellow
    exit 1
}

Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.*)$') {
        $name  = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"')
        if ($value) {
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
            $shown = if ($name -match 'URL|KEY|TOKEN|PASSWORD') { "(set, $($value.Length) chars)" } else { $value }
            Write-Host "  $name = $shown"
        }
    }
}
