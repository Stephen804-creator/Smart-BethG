from .provider_base import ProviderBase
class SmartBethGFreeProvider(ProviderBase):
 name="smartbethg_free"
 def generate(self,messages,model,**kwargs): raise NotImplementedError("Connect the platform's configured free model here.")
