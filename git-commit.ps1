# PowerShell script for git commits
param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

git commit -m $Message

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Commit successful!" -ForegroundColor Green
} else {
    Write-Host "❌ Commit failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}
