class GoogleAuthService:
    def __init__(self,client_id=None,client_secret=None): self.client_id=client_id; self.client_secret=client_secret
    def authorization_url(self,redirect_uri): raise NotImplementedError("Configure Google OIDC before enabling login.")
    def exchange_code(self,code,redirect_uri): raise NotImplementedError("Configure Google OIDC before enabling login.")
