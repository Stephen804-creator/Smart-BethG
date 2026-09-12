from urllib.request import Request,urlopen
class NetworkTool:
    def get(self,permit,url,timeout=15):
        if permit.action!="network.request": raise PermissionError("Invalid permit.")
        with urlopen(Request(url,headers={"User-Agent":"SmartBethG/1.0"}),timeout=timeout) as r: return r.read().decode("utf-8",errors="replace")
