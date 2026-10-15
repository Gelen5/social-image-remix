# Local runtime (Windows)

Installed for social-image-remix:
- Python: C:\Users\ALIENWARE\AppData\Local\Programs\Python\Python313\python.exe
- Skill virtual environment: C:\Users\ALIENWARE\.codex\skills\social-image-remix\.venv\Scripts\python.exe
- Node.js: C:\Users\ALIENWARE\AppData\Local\social-image-remix\node\node-v22.23.3-win-x64\node.exe
- OpenCLI: C:\Users\ALIENWARE\AppData\Roaming\npm\opencli.ps1

Use the skill virtual environment for all Python scripts. In an already-running PowerShell session, refresh PATH before browser scripts:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
$env:PYTHONIOENCODING = 'utf-8'
& 'C:\Users\ALIENWARE\.codex\skills\social-image-remix\.venv\Scripts\python.exe' 'C:\Users\ALIENWARE\.codex\skills\social-image-remix\scripts\browser_extract.py' doctor
```

Browser Bridge connectivity depends on Chrome running with the OpenCLI extension enabled. Platform login remains in Chrome.
