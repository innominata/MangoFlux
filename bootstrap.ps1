$ErrorActionPreference = 'Stop'
$dir = Join-Path $env:LOCALAPPDATA 'MangoFlux'
$python = Join-Path $dir 'python'
$installer = Join-Path $env:TEMP 'mangoflux-python-3.12.10.exe'
try {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Write-Host 'Downloading the private Python runtime (about 26 MB)...'
  Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer
  $signature = Get-AuthenticodeSignature $installer
  if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Python installer signature could not be verified.' }
  Write-Host 'Installing the runtime for this user...'
  $p = Start-Process -FilePath $installer -ArgumentList @('/quiet','InstallAllUsers=0',"TargetDir=`"$python`"",'Include_test=0','Include_pip=1','Include_tcltk=1','PrependPath=0','Include_launcher=0','Shortcuts=0') -Wait -PassThru
  if ($p.ExitCode -ne 0 -or !(Test-Path (Join-Path $python 'pythonw.exe'))) { throw "Python installer failed ($($p.ExitCode))." }
} catch { Write-Host $_ -ForegroundColor Red; exit 1 } finally { Remove-Item -LiteralPath $installer -ErrorAction SilentlyContinue }
