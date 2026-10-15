[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repoUrl = 'https://github.com/Gelen5/social-image-remix.git'
$skillRoot = $PSScriptRoot
$cache = Join-Path $skillRoot '.update-cache'
$statePath = Join-Path $skillRoot '.update-state.json'
# This installed copy was compared against this upstream revision on 2026-10-15.
$initialBase = 'afae0930b653170dbd5287d981811fe6ee65ab8e'

function Invoke-Git([string[]]$GitArgs) {
    $result = & git @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') failed: $result" }
    return $result
}
function Hash-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath (Join-Path $cache '.git'))) {
    if (Test-Path -LiteralPath $cache) { Remove-Item -LiteralPath $cache -Recurse -Force }
    Invoke-Git @('clone', '--no-checkout', '--filter=blob:none', $repoUrl, $cache) | Out-Null
}
Invoke-Git @('-C', $cache, 'fetch', '--depth=1', 'origin', '+refs/heads/main:refs/remotes/origin/main') | Out-Null
$latest = (Invoke-Git @('-C', $cache, 'rev-parse', 'refs/remotes/origin/main') | Select-Object -Last 1).Trim()
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    $base = [string]$state.revision
} else {
    $base = $initialBase
}
if ($base -eq $latest) {
    @{ revision = $latest; checked_utc = [DateTime]::UtcNow.ToString('o'); source = $repoUrl } |
        ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
    Write-Output "social-image-remix is current at $latest"
    exit 0
}

Invoke-Git @('-C', $cache, 'fetch', '--depth=1', 'origin', $base) | Out-Null
$work = Join-Path ([IO.Path]::GetTempPath()) ('social-image-remix-update-' + [guid]::NewGuid().ToString('N'))
$baseTree = Join-Path $work 'base'
$newTree = Join-Path $work 'latest'
New-Item -ItemType Directory -Path $work | Out-Null
$conflicts = [System.Collections.Generic.List[string]]::new()
try {
    Invoke-Git @('-C', $cache, 'worktree', 'add', '--detach', $baseTree, $base) | Out-Null
    Invoke-Git @('-C', $cache, 'worktree', 'add', '--detach', $newTree, $latest) | Out-Null
    $skip = @('.git', '.venv', '.update-cache', '__pycache__')
    $baseFiles = Get-ChildItem -LiteralPath $baseTree -Recurse -File | Where-Object {
        $rel = $_.FullName.Substring($baseTree.Length + 1)
        $parts = $rel -split '[\\/]'
        -not ($parts | Where-Object { $_ -in $skip }) -and $_.Extension -ne '.pyc'
    }
    $newFiles = Get-ChildItem -LiteralPath $newTree -Recurse -File | Where-Object {
        $rel = $_.FullName.Substring($newTree.Length + 1)
        $parts = $rel -split '[\\/]'
        -not ($parts | Where-Object { $_ -in $skip }) -and $_.Extension -ne '.pyc'
    }
    $baseMap = @{}; foreach ($f in $baseFiles) { $baseMap[$f.FullName.Substring($baseTree.Length + 1)] = $f.FullName }
    $newMap = @{}; foreach ($f in $newFiles) { $newMap[$f.FullName.Substring($newTree.Length + 1)] = $f.FullName }

    foreach ($rel in $baseMap.Keys) {
        $localPath = Join-Path $skillRoot $rel
        if (-not $newMap.ContainsKey($rel)) {
            if ((Hash-File $localPath) -eq (Hash-File $baseMap[$rel])) {
                Remove-Item -LiteralPath $localPath -Force
            } else { $conflicts.Add("upstream deleted locally customized file: $rel") }
            continue
        }
        $baseHash = Hash-File $baseMap[$rel]
        $localHash = Hash-File $localPath
        $newHash = Hash-File $newMap[$rel]
        if ($localHash -eq $newHash) { continue }
        if ($localHash -eq $baseHash) {
            $target = Split-Path -Parent $localPath
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            Copy-Item -LiteralPath $newMap[$rel] -Destination $localPath -Force
        } elseif ($newHash -ne $baseHash) {
            # Try a standard three-way text merge; on conflict keep local content.
            $mergeOut = Join-Path $work 'merged.tmp'
            $merged = & git merge-file -p $localPath $baseMap[$rel] $newMap[$rel] 2>&1
            $mergeExit = $LASTEXITCODE
            if ($mergeExit -eq 0) {
                $merged | Set-Content -LiteralPath $mergeOut -Encoding utf8
                Copy-Item -LiteralPath $mergeOut -Destination $localPath -Force
            } else { $conflicts.Add("merge conflict (local kept): $rel") }
        }
    }
    foreach ($rel in $newMap.Keys) {
        if (-not $baseMap.ContainsKey($rel)) {
            $localPath = Join-Path $skillRoot $rel
            if (-not (Test-Path -LiteralPath $localPath)) {
                $target = Split-Path -Parent $localPath
                New-Item -ItemType Directory -Path $target -Force | Out-Null
                Copy-Item -LiteralPath $newMap[$rel] -Destination $localPath
            } else { $conflicts.Add("new upstream file already exists locally: $rel") }
        }
    }
    @{ revision = $latest; checked_utc = [DateTime]::UtcNow.ToString('o'); source = $repoUrl } |
        ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
} finally {
    & git -C $cache worktree remove --force $baseTree 2>$null | Out-Null
    & git -C $cache worktree remove --force $newTree 2>$null | Out-Null
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($conflicts.Count) {
    Write-Output "Fetched $latest; local files were preserved where merge conflicts occurred:"
    $conflicts | ForEach-Object { Write-Output " - $_" }
    exit 2
}
Write-Output "Updated social-image-remix from $base to $latest"
