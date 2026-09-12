from .provider_base import ProviderBase
class GoogleProvider(ProviderBase):
 name="google"
 def __init__(self,api_key): self.api_key=api_key
 def generate(self,messages,model,**kwargs): raise NotImplementedError("Install/configure the Google Gemini SDK in the deployment environment.")
