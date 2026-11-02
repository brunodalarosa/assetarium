' Starts Assetarium with a console window that follows this session's log live.
' Arguments go to the app: --verbose (debug lines) or --log-level debug|info|warning|error.
Option Explicit
Dim shell, fs, root, python, console, script, args, i
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = fs.BuildPath(root, ".venv-mcp\Scripts\pythonw.exe")
console = fs.BuildPath(root, ".venv-mcp\Scripts\python.exe")
script = fs.BuildPath(root, "scripts\asset-desktop.pyw")
If Not fs.FileExists(python) Or Not fs.FileExists(console) Then
    MsgBox "The prepared desktop runtime is missing. See docs\gui\README.md. Startup does not install dependencies.", 16, "Assetarium"
    WScript.Quit 1
End If
args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " " & Chr(34) & WScript.Arguments(i) & Chr(34)
Next
shell.CurrentDirectory = root
shell.Environment("Process")("PYTHONPATH") = fs.BuildPath(root, "src")
' The console starts first and waits for the app's new session, so it shows the session from its first line.
shell.Run "cmd /k ""title Assetarium log && """ & console & """ -m local_asset_library.cli logs --next --level debug""", 1, False
WScript.Sleep 300
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & script & Chr(34) & args, 1, False
