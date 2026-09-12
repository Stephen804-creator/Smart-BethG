from .provider_base import ProviderBase
class OpenAIProvider(ProviderBase):
 name="openai"
 def __init__(self,api_key): self.api_key=api_key
 def generate(self,messages,model,**kwargs): raise NotImplementedError("Install/configure the OpenAI SDK in the deployment environment.")
