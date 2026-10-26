# Stop and remove the app container if it exists.
$Container = "pm-app"

docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    docker rm -f $Container | Out-Null
    Write-Host "Stopped $Container"
} else {
    Write-Host "$Container is not running"
}
