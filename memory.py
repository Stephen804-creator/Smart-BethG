class Memory:
 def __init__(self): self._store={}
 def remember(self,user_id,key,value): self._store.setdefault(user_id,{})[key]=value
 def recall(self,user_id,key): return self._store.get(user_id,{}).get(key)
