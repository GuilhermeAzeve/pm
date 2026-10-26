# Build the image and run the app container on http://localhost:8000.
$Root = Split-Path -Parent $PSScriptRoot
$Image = "pm-app"
$Container = "pm-app"
$Volume = "pm-data"

docker build -t $Image $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    docker rm -f $Container | Out-Null
}

$EnvArgs = @()
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    $EnvArgs = @("--env-file", $EnvFile)
}

docker run -d --name $Container -p 8000:8000 `
    -v "${Volume}:/data" -e DATABASE_PATH=/data/pm.db `
    @EnvArgs $Image | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Running at http://localhost:8000"
