param(
    [string]$VenvDir = ".venv",
    [string]$OutputFile = "requirements.lock.txt"
)

& "$VenvDir\Scripts\python.exe" -m pip freeze | Set-Content -Path $OutputFile -Encoding utf8
Write-Host "Lock file written to $OutputFile"
