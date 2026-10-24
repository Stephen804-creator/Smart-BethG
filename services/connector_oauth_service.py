"""Single-use, owner-bound OAuth state and provider token exchange."""
import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import httpx
from database import get_connection
from services.connector_service import CATALOG, ConnectorInstallationService
from services.connector_secrets import ConnectorSecretStore
import config

PROVIDERS = {
 "github": {
  "authorize":"https://github.com/login/oauth/authorize", "token":"https://github.com/login/oauth/access_token",
  "scopes":["repo","read:user"], "client_id":lambda:config.GITHUB_OAUTH_CLIENT_ID,
  "client_secret":lambda:config.GITHUB_OAUTH_CLIENT_SECRET,
 },
 "google_drive": {
  "authorize":"https://accounts.google.com/o/oauth2/v2/auth", "token":"https://oauth2.googleapis.com/token",
  "scopes":["https://www.googleapis.com/auth/drive.readonly"], "client_id":lambda:config.GOOGLE_OAUTH_CLIENT_ID,
  "client_secret":lambda:config.GOOGLE_OAUTH_CLIENT_SECRET,
 },
 "slack": {
  "authorize":"https://slack.com/oauth/v2/authorize", "token":"https://slack.com/api/oauth.v2.access",
  "scopes":["chat:write","channels:read"], "client_id":lambda:config.SLACK_OAUTH_CLIENT_ID,
  "client_secret":lambda:config.SLACK_OAUTH_CLIENT_SECRET,
 },
}

class ConnectorOAuthService:
 def __init__(self, secrets_store=None):
  self.secrets=secrets_store or ConnectorSecretStore()
  self.installations=ConnectorInstallationService()

 def configured(self, provider):
  cfg=PROVIDERS.get(provider)
  return bool(cfg and cfg["client_id"]() and cfg["client_secret"]())

 def start(self, user_id, installation_id, provider, redirect_uri):
  if provider not in PROVIDERS or provider not in CATALOG or provider=="smartbethg":
   raise ValueError("Unsupported OAuth connector.")
  if not self.configured(provider):
   raise RuntimeError("This provider is not configured by the deployment operator.")
  if config.SECRET_KEY_IS_EPHEMERAL:
   raise RuntimeError("Set a stable SMART_BETHG_SECRET_KEY before connecting external accounts.")
  installation=self.installations.get_for_user(user_id,installation_id)
  if not installation or installation["connector_key"]!=provider:
   raise LookupError("Connector installation not found for this user.")
  state=secrets.token_urlsafe(32)
  verifier=secrets.token_urlsafe(48) if provider=="google_drive" else None
  digest=hashlib.sha256(state.encode()).hexdigest()
  conn=get_connection()
  try:
   conn.execute("INSERT INTO connector_oauth_states(state_hash,user_id,installation_id,connector_key,verifier,expires_at) VALUES (?,?,?,?,?,?)",
     (digest,user_id,installation_id,provider,verifier,datetime.now(timezone.utc)+timedelta(minutes=10)))
   conn.commit()
  finally: conn.close()
  cfg=PROVIDERS[provider]
  params={"client_id":cfg["client_id"](),"redirect_uri":redirect_uri,"state":state}
  if provider=="github":
   params["scope"]=" ".join(cfg["scopes"])
  elif provider=="google_drive":
   challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
   params.update({"response_type":"code","scope":" ".join(cfg["scopes"]),"access_type":"offline","prompt":"consent",
                  "code_challenge":challenge,"code_challenge_method":"S256"})
  else:
   params["scope"]=" ".join(cfg["scopes"])
  return cfg["authorize"]+"?"+urlencode(params)

 def callback(self, provider, code, state, redirect_uri):
  if provider not in PROVIDERS or not code or not state:
   raise ValueError("Invalid OAuth callback.")
  digest=hashlib.sha256(state.encode()).hexdigest()
  conn=get_connection()
  try:
   row=conn.execute("""UPDATE connector_oauth_states SET consumed_at=CURRENT_TIMESTAMP
      WHERE state_hash=? AND connector_key=? AND consumed_at IS NULL AND expires_at>CURRENT_TIMESTAMP
      RETURNING user_id,installation_id,connector_key,verifier""",(digest,provider)).fetchone()
   conn.commit()
  finally: conn.close()
  if not row:
   raise ValueError("OAuth state is invalid, expired, or already used.")
  cfg=PROVIDERS[provider]
  data={"client_id":cfg["client_id"](),"client_secret":cfg["client_secret"](),"code":code,"redirect_uri":redirect_uri}
  if provider=="google_drive":
   data["grant_type"]="authorization_code"
   data["code_verifier"]=row["verifier"]
  headers={"Accept":"application/json"}
  if provider=="github": headers["Accept"]="application/json"
  try:
   response=httpx.post(cfg["token"],data=data,headers=headers,timeout=15.0)
   response.raise_for_status()
   token=response.json()
  except Exception as exc:
   raise RuntimeError("Provider token exchange failed.") from exc
  if provider=="slack" and not token.get("ok"):
   raise RuntimeError("Slack did not authorize the connection.")
  access=token.get("access_token")
  if not access:
   raise RuntimeError("Provider returned no access token.")
  account=""
  scopes=[]
  if provider=="github":
   profile=httpx.get("https://api.github.com/user",headers={"Authorization":"Bearer "+access,"Accept":"application/vnd.github+json"},timeout=15.0)
   profile.raise_for_status(); account=profile.json().get("login","")
   scopes=[s for s in profile.headers.get("X-OAuth-Scopes","").split(", ") if s]
  elif provider=="google_drive":
   profile=httpx.get("https://www.googleapis.com/drive/v3/about",params={"fields":"user(emailAddress,displayName)"},
      headers={"Authorization":"Bearer "+access},timeout=15.0)
   profile.raise_for_status(); user=profile.json().get("user",{}); account=user.get("emailAddress","")
   scopes=token.get("scope","").split()
  else:
   account=(token.get("authed_user") or {}).get("id") or (token.get("team") or {}).get("name","")
   scopes=(token.get("scope") or "").split(",")
  credential={"access_token":access}
  if token.get("refresh_token"): credential["refresh_token"]=token["refresh_token"]
  if token.get("token_type"): credential["token_type"]=token["token_type"]
  expires_at=None
  if token.get("expires_in"):
   expires_at=datetime.now(timezone.utc)+timedelta(seconds=int(token["expires_in"]))
  self.secrets.put(row["installation_id"],credential,account,scopes,expires_at)
  conn=get_connection()
  try:
   conn.execute("UPDATE connector_installations SET status='connected',credential_ref=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
    ("encrypted-db:"+str(row["installation_id"]),row["installation_id"],row["user_id"]))
   conn.commit()
  finally: conn.close()
  return {"connector_key":provider,"installation_id":row["installation_id"],"connected":True,"account":account or None,"scopes":scopes}

 def disconnect(self, user_id, installation_id):
  installation=self.installations.get_for_user(user_id,installation_id)
  if not installation: return False
  stored=self.secrets.get(installation_id)
  if stored:
   token=stored["credentials"].get("access_token","")
   try:
    if installation["connector_key"]=="slack" and token:
     httpx.post("https://slack.com/api/auth.revoke",headers={"Authorization":"Bearer "+token},timeout=5.0)
    elif installation["connector_key"]=="google_drive" and token:
     httpx.post("https://oauth2.googleapis.com/revoke",params={"token":token},timeout=5.0)
   except Exception:
    pass
  self.secrets.delete(installation_id)
  conn=get_connection()
  try:
   conn.execute("UPDATE connector_installations SET status='disconnected',credential_ref=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(installation_id,user_id))
   conn.commit()
  finally: conn.close()
  return True
