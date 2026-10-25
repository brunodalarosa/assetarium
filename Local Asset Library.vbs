Option Explicit
Dim shell, fs, root, python, script
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = fs.BuildPath(root, ".venv-mcp\Scripts\pythonw.exe")
script = fs.BuildPath(root, "scripts\asset-desktop.pyw")
If Not fs.FileExists(python) Then
    MsgBox "The prepared desktop runtime is missing. See docs\gui\README.md. Startup does not install dependencies.", 16, "Local Asset Library"
    WScript.Quit 1
End If
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & script & Chr(34), 1, False
