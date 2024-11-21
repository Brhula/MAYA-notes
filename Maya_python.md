## Maya Pyton code


Check if QuickTime plug-in is installed:
```Python
# Pyton code to check for if Quicktime is installed (Windows)
import os
def getQuickTime():
    if os.name == 'nt':
        installed = os.path.exists(os.environ['ProgramFiles(x86)'] + "\\QuickTime\\QuickTimePlayer.exe")
        return installed
    else:
        return None

```
