from execution.command_runner import CommandRunner
class TerminalTool:
    def __init__(self): self.runner=CommandRunner()
    def execute(self,permit,program,args,cwd): return self.runner.run(permit,program,args,cwd=cwd)
