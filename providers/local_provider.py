from .provider_base import ProviderBase
class LocalProvider(ProviderBase):
 name="local"
 def __init__(self,endpoint="http://127.0.0.1:11434"): self.endpoint=endpoint
 def generate(self,messages,model,**kwargs): raise NotImplementedError("Connect the selected local runtime here.")
