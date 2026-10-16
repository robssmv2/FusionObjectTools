[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

if (Get-Process -Name Fusion360 -ErrorAction SilentlyContinue) {
    throw 'Close Autodesk Fusion before installing or updating Fusion Object Tools.'
}

$source = Join-Path $PSScriptRoot 'ObjectTypeInspector'
$requiredFiles = @('ObjectTypeInspector.py', 'ObjectTypeInspector.manifest', 'index.html', 'README.md')
foreach ($name in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $source $name) -PathType Leaf)) {
        throw "The package is incomplete: missing $name. Extract the entire ZIP before installing."
    }
}
$manifestJson = Get-Content -LiteralPath (Join-Path $source 'ObjectTypeInspector.manifest') -Raw
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $manifest = ConvertFrom-Json -InputObject $manifestJson -AsHashtable
}
else {
    Add-Type -AssemblyName System.Web.Extensions
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $manifest = $serializer.DeserializeObject($manifestJson)
}
if ($manifest.id -ne 'ObjectTypeInspector' -or $manifest.type -ne 'addin') {
    throw 'The package manifest is not for the ObjectTypeInspector add-in.'
}

$addInsRoot = Join-Path $env:APPDATA 'Autodesk\Autodesk Fusion 360\API\AddIns'
$destination = Join-Path $addInsRoot 'ObjectTypeInspector'
$id = [guid]::NewGuid().ToString('N')
$staging = Join-Path $addInsRoot ".ObjectTypeInspector-install-$id"
$backup = $null
New-Item -ItemType Directory -Path $staging -Force | Out-Null

try {
    foreach ($name in $requiredFiles) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination $staging
    }
    if (Test-Path -LiteralPath $destination) {
        $backupRoot = Join-Path $env:APPDATA 'FusionObjectTools\Backups'
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $backup = Join-Path $backupRoot "ObjectTypeInspector-$id"
        Move-Item -LiteralPath $destination -Destination $backup
    }
    Move-Item -LiteralPath $staging -Destination $destination
}
catch {
    $installError = $_
    if ($backup -and (Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $destination)) {
        Move-Item -LiteralPath $backup -Destination $destination
        Write-Warning 'The previous installation was restored.'
    }
    Write-Warning "Installation did not complete. Any staged files remain at: $staging"
    throw $installError
}

Write-Output "Installed Fusion Object Tools $($manifest.version) to:"
Write-Output $destination
if ($backup) {
    Write-Output "Previous installation backed up to: $backup"
}
Write-Output 'Open Fusion, press Shift+S, select Add-Ins > ObjectTypeInspector, and click Run.'
Write-Output 'Enable Run on Startup. Dissolve All is under Design > Solid > Modify.'
