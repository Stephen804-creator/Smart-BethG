from .provider_base import ProviderBase
class AnthropicProvider(ProviderBase):
 name="anthropic"
 def __init__(self,api_key): self.api_key=api_key
 def generate(self,messages,model,**kwargs): raise NotImplementedError("Install/configure the Anthropic SDK in the deployment environment.")
