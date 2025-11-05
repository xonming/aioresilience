# Git Helper Script
# Usage examples:
#   .\git-helper.ps1 commit "Your message"
#   .\git-helper.ps1 push
#   .\git-helper.ps1 acp "Your message"  (add, commit, push)

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("commit", "push", "acp", "status")]
    [string]$Action,
    
    [Parameter(Position=1)]
    [string]$Message
)

function Show-Status {
    Write-Host "`n📊 Git Status:" -ForegroundColor Cyan
    git status
}

function Do-Commit {
    if ([string]::IsNullOrWhiteSpace($Message)) {
        Write-Host "❌ Commit message required!" -ForegroundColor Red
        Write-Host "Usage: .\git-helper.ps1 commit 'Your message'" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "`n💾 Committing changes..." -ForegroundColor Cyan
    git commit -m $Message
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Commit successful!" -ForegroundColor Green
    } else {
        Write-Host "❌ Commit failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Do-Push {
    Write-Host "`n🚀 Pushing to remote..." -ForegroundColor Cyan
    git push
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Push successful!" -ForegroundColor Green
    } else {
        Write-Host "❌ Push failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Do-AddCommitPush {
    if ([string]::IsNullOrWhiteSpace($Message)) {
        Write-Host "❌ Commit message required!" -ForegroundColor Red
        Write-Host "Usage: .\git-helper.ps1 acp 'Your message'" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "`n📦 Adding all changes..." -ForegroundColor Cyan
    git add .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Git add failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    
    Do-Commit
    Do-Push
}

# Execute action
switch ($Action) {
    "commit" { Do-Commit }
    "push" { Do-Push }
    "acp" { Do-AddCommitPush }
    "status" { Show-Status }
}

Write-Host ""
