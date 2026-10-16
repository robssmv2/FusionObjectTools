[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$manifestJson = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'ObjectTypeInspector\ObjectTypeInspector.manifest') -Raw
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $manifest = ConvertFrom-Json -InputObject $manifestJson -AsHashtable
}
else {
    Add-Type -AssemblyName System.Web.Extensions
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $manifest = $serializer.DeserializeObject($manifestJson)
}
$name = "FusionObjectTools-$($manifest.version)-Windows"
$dist = Join-Path $PSScriptRoot 'dist'
$stage = Join-Path ([System.IO.Path]::GetTempPath()) "$name-$([guid]::NewGuid().ToString('N'))"
$payload = Join-Path $stage 'ObjectTypeInspector'
New-Item -ItemType Directory -Path $payload -Force | Out-Null
New-Item -ItemType Directory -Path $dist -Force | Out-Null
try {
    foreach ($file in @('ObjectTypeInspector.py', 'ObjectTypeInspector.manifest', 'index.html', 'README.md')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot "ObjectTypeInspector\$file") -Destination $payload
    }
    foreach ($file in @('Install.ps1', 'README.md')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $stage
    }
    $archive = Join-Path $dist "$name.zip"
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $archive -Force
    $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $name.zip" | Set-Content -LiteralPath "$archive.sha256" -Encoding ASCII
    Write-Output $archive
    Write-Output "$archive.sha256"
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
