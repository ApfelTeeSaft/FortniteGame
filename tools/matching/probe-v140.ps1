param(
    [string]$CompilerDirectory = "${env:ProgramFiles(x86)}\Microsoft Visual Studio 14.0\VC\bin\amd64"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$source = Join-Path $root 'FortniteGameCode/Probe.cpp'
$out = (New-Item -ItemType Directory -Force (Join-Path $root 'local-output/v140')).FullName
$compiler = Join-Path $CompilerDirectory 'cl.exe'
$linker = Join-Path $CompilerDirectory 'link.exe'
$object = Join-Path $out 'Probe.obj'
$dll = Join-Path $out 'Probe.dll'

& $compiler /nologo /c /O2 /Ob2 /Gy /MD /GS /fp:precise /EHsc "/Fo$object" $source
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $linker /nologo /DLL /NOENTRY /NODEFAULTLIB /INCREMENTAL:NO /OPT:REF /OPT:NOICF /MACHINE:X64 "/OUT:$dll" $object
exit $LASTEXITCODE
