# One-time, owner-approved migration. Existing destination folders are never merged.
$ErrorActionPreference = 'Stop'
$relocationProject = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$relocationSource = (Resolve-Path -LiteralPath (Join-Path $relocationProject 'models')).Path
$relocationTarget = (Resolve-Path -LiteralPath 'C:\BrunoOS\Local-models').Path
if ($relocationSource -ne 'C:\BrunoOS\Local-Asset-Library\models' -or $relocationTarget -ne 'C:\BrunoOS\Local-models') { throw 'Unexpected migration roots' }
$relocationReportDir = Join-Path $relocationProject 'data\model-relocation'
New-Item -ItemType Directory -Path $relocationReportDir -Force | Out-Null
$relocationReport = @{ source = $relocationSource; destination = $relocationTarget; items = @(); faults = @() }
$relocationEvidence = Join-Path $relocationReportDir 'move.json'
if (Test-Path -LiteralPath $relocationEvidence) { throw 'Existing migration evidence retained; no automatic retry' }
foreach ($relocationName in @('qwen3-vl-2b','embeddinggemma-2')) {
    $relocationItem = @{ name = $relocationName; status = 'pending'; before = @(); after = @() }
    $relocationReport.items += $relocationItem
    try {
        $relocationFrom = (Resolve-Path -LiteralPath (Join-Path $relocationSource $relocationName)).Path
        $relocationTo = [IO.Path]::GetFullPath((Join-Path $relocationTarget $relocationName))
        if ([IO.Path]::GetDirectoryName($relocationFrom) -ne $relocationSource -or [IO.Path]::GetDirectoryName($relocationTo) -ne $relocationTarget) { throw 'Move crosses approved roots' }
        if (Test-Path -LiteralPath $relocationTo) { throw 'Destination already exists; no merge or overwrite' }
        if ((Get-Item -LiteralPath $relocationFrom).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Source is a link' }
        $relocationFiles = @(Get-ChildItem -LiteralPath $relocationFrom -Recurse -File -Force)
        if (@(Get-ChildItem -LiteralPath $relocationFrom -Recurse -Force -Attributes ReparsePoint).Count) { throw 'Nested source link' }
        foreach ($relocationFile in $relocationFiles) {
            $relocationItem.before += @{ path = [IO.Path]::GetRelativePath($relocationFrom,$relocationFile.FullName); bytes = $relocationFile.Length; sha256 = (Get-FileHash -LiteralPath $relocationFile.FullName -Algorithm SHA256).Hash }
        }
        $relocationReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $relocationEvidence -Encoding utf8
        Move-Item -LiteralPath $relocationFrom -Destination $relocationTo
        foreach ($relocationFile in @(Get-ChildItem -LiteralPath $relocationTo -Recurse -File -Force)) {
            $relocationItem.after += @{ path = [IO.Path]::GetRelativePath($relocationTo,$relocationFile.FullName); bytes = $relocationFile.Length; sha256 = (Get-FileHash -LiteralPath $relocationFile.FullName -Algorithm SHA256).Hash }
        }
        if ($relocationItem.before.Count -ne $relocationItem.after.Count) { throw 'File count mismatch after move' }
        foreach ($relocationEntry in $relocationItem.before) {
            $relocationMatch = @($relocationItem.after | Where-Object { $_.path -eq $relocationEntry.path -and $_.bytes -eq $relocationEntry.bytes -and $_.sha256 -eq $relocationEntry.sha256 })
            if ($relocationMatch.Count -ne 1) { throw ('Hash mismatch: ' + $relocationEntry.path) }
        }
        $relocationItem.status = 'verified'
    } catch {
        $relocationItem.status = 'faulty'
        $relocationItem.reason = $_.Exception.Message
        $relocationReport.faults += @{ item = $relocationName; reason = $_.Exception.Message }
    }
    $relocationReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $relocationEvidence -Encoding utf8
}
$relocationReport.items | Select-Object name,status,reason | ConvertTo-Json
if ($relocationReport.faults.Count) { exit 1 }
