import subprocess
class GitTool:
    def status(self,permit,cwd):
        if permit.action!="git.read": raise PermissionError("Invalid permit.")
        return subprocess.run(["git","status","--short"],cwd=cwd,capture_output=True,text=True,timeout=30,check=False).stdout
