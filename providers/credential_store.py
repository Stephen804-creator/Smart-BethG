class CredentialStore:
 def __init__(self): self._refs={}
 def put(self,user_id,provider,secret):
  ref=f"{user_id}:{provider}"; self._refs[ref]=secret; return ref
 def get(self,user_id,ref): return self._refs.get(ref) if ref.startswith(f"{user_id}:") else None
