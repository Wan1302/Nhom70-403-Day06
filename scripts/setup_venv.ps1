param(
    [string]$PythonCmd = "python",
    [string]$VenvDir = ".venv"
)

& $PythonCmd -m venv $VenvDir
& "$VenvDir\Scripts\python.exe" -m pip install --upgrade pip
& "$VenvDir\Scripts\pip.exe" install -r requirements.txt

Write-Host ""
Write-Host "Done. Activate with:"
Write-Host ".\\$VenvDir\\Scripts\\Activate.ps1"
