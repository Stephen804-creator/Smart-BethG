import subprocess
class DockerTool:
    def run(self,permit,args,cwd=None):
        if permit.action!="docker.run": raise PermissionError("Invalid permit.")
        if not isinstance(args,list) or any(not isinstance(x,str) for x in args): raise TypeError("Docker args must be strings.")
        return subprocess.run(["docker",*args],cwd=cwd,capture_output=True,text=True,timeout=60,check=False)
