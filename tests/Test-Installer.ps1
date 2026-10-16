$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$archive = Join-Path $project 'dist\FusionObjectTools-1.0.0-Windows.zip'
$scratch = Join-Path ([System.IO.Path]::GetTempPath()) "FusionObjectTools-test-$([guid]::NewGuid().ToString('N'))"
$originalAppData = $env:APPDATA
$testState = @{ SimulateFusion = $false }

function Get-Process {
    param($Name, $ErrorAction)
    if ($testState.SimulateFusion) {
        return [pscustomobject]@{ ProcessName = 'Fusion360' }
    }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

try {
    $extract = Join-Path $scratch 'Extracted'
    Expand-Archive -LiteralPath $archive -DestinationPath $extract
    $env:APPDATA = Join-Path $scratch 'AppData'
    $installer = Join-Path $extract 'Install.ps1'
    $destination = Join-Path $env:APPDATA 'Autodesk\Autodesk Fusion 360\API\AddIns\ObjectTypeInspector'
    & $installer | Out-Null
    foreach ($name in @('ObjectTypeInspector.py', 'ObjectTypeInspector.manifest', 'index.html', 'README.md')) {
        $expected = (Get-FileHash -LiteralPath (Join-Path $extract "ObjectTypeInspector\$name")).Hash
        $actual = (Get-FileHash -LiteralPath (Join-Path $destination $name)).Hash
        Assert-True ($actual -eq $expected) "Installed file differs: $name"
    }
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $destination 'tests'))) 'Tests leaked into runtime install.'
    Write-Output 'PASS: clean install and exact runtime files'

    Set-Content -LiteralPath (Join-Path $destination 'previous-version.txt') -Value 'keep me'
    & $installer | Out-Null
    $backups = @(Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'FusionObjectTools\Backups') -Directory)
    Assert-True ($backups.Count -eq 1) 'Expected one backup.'
    Assert-True (Test-Path -LiteralPath (Join-Path $backups[0].FullName 'previous-version.txt')) 'Previous installation was not preserved.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $destination 'previous-version.txt'))) 'Old files leaked into update.'
    Write-Output 'PASS: update backs up the entire previous installation'

    $testState.SimulateFusion = $true
    $blocked = $false
    try { & $installer | Out-Null }
    catch { $blocked = $_.Exception.Message -like '*Close Autodesk Fusion*' }
    Assert-True $blocked 'Installer did not block installation with Fusion running.'
    $testState.SimulateFusion = $false
    Write-Output 'PASS: refuses to install while Fusion is running'

    Remove-Item -LiteralPath (Join-Path $extract 'ObjectTypeInspector\index.html')
    $blocked = $false
    try { & $installer | Out-Null }
    catch { $blocked = $_.Exception.Message -like '*package is incomplete*' }
    Assert-True $blocked 'Incomplete package was accepted.'
    Assert-True (Test-Path -LiteralPath (Join-Path $destination 'index.html')) 'Existing installation was damaged.'
    Write-Output 'PASS: rejects incomplete package without changing installation'
}
finally {
    $env:APPDATA = $originalAppData
    if (Test-Path -LiteralPath $scratch) {
        Remove-Item -LiteralPath $scratch -Recurse -Force
    }
}
