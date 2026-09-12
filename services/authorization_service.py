class AuthorizationService:
    def require(self,user,permission,permissions):
        if permission not in set(permissions): raise PermissionError("Permission denied.")
        return True
