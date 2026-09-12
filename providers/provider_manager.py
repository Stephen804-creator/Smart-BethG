from .smartbethg_free import SmartBethGFreeProvider
class ProviderManager:
 def __init__(self): self.platform={"smartbethg_free":SmartBethGFreeProvider()}; self.user={}
 def register_user_provider(self,user_id,name,provider): self.user.setdefault(user_id,{})[name]=provider
 def get(self,user_id,name): return self.user.get(user_id,{}).get(name) or self.platform.get(name)
