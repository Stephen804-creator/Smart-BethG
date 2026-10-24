"""Live, bounded, read/write provider adapters for authorized OAuth installations."""
import httpx
from datetime import datetime, timedelta, timezone
import config
from services.connector_secrets import ConnectorSecretStore

class ProviderAdapter:
 def __init__(self, provider, secrets_store=None):
  self.provider=provider
  self.secrets=secrets_store or ConnectorSecretStore()
 def execute(self, action, arguments, context):
  stored=self.secrets.get(context["installation_id"])
  if not stored: return {"success":False,"status":"unavailable","detail":"Provider credentials are missing."}
  credentials=stored["credentials"]
  expires=stored.get("expires_at")
  if isinstance(expires,str):
   try: expires=datetime.fromisoformat(expires.replace("Z","+00:00"))
   except ValueError: expires=None
  if self.provider=="google_drive" and expires and expires <= datetime.now(timezone.utc)+timedelta(seconds=60):
   refresh_token=credentials.get("refresh_token")
   if not refresh_token:
    return {"success":False,"status":"reauthorization_required","detail":"Reconnect Google Drive to renew access."}
   try:
    response=httpx.post("https://oauth2.googleapis.com/token",data={
     "client_id":config.GOOGLE_OAUTH_CLIENT_ID,"client_secret":config.GOOGLE_OAUTH_CLIENT_SECRET,
     "refresh_token":refresh_token,"grant_type":"refresh_token"},timeout=15.0)
    response.raise_for_status()
    renewed=response.json()
    if not renewed.get("access_token"): raise ValueError("Missing refreshed access token.")
    credentials["access_token"]=renewed["access_token"]
    new_expiry=datetime.now(timezone.utc)+timedelta(seconds=int(renewed.get("expires_in",3600)))
    self.secrets.put(context["installation_id"],credentials,stored.get("provider_account"),stored.get("scopes"),new_expiry)
    stored=self.secrets.get(context["installation_id"])
    credentials=stored["credentials"]
   except (httpx.RequestError,httpx.HTTPStatusError,ValueError):
    return {"success":False,"status":"reauthorization_required","detail":"Google Drive access could not be refreshed; reconnect the account."}
  token=credentials.get("access_token")
  if not token: return {"success":False,"status":"unavailable","detail":"Provider credentials are missing."}
  try:
   if self.provider=="github": result=self._github(token,action,arguments,context)
   elif self.provider=="google_drive": result=self._drive(token,action,arguments)
   elif self.provider=="slack": result=self._slack(token,action,arguments,context)
   else: return {"success":False,"status":"unsupported"}
   return {"success":True,"status":"completed","data":result}
  except httpx.HTTPStatusError as exc:
   code=exc.response.status_code
   return {"success":False,"status":"provider_error","detail":f"Provider returned HTTP {code}."}
  except (httpx.RequestError,ValueError,KeyError):
   return {"success":False,"status":"provider_error","detail":"Provider request failed."}
 def _github(self,token,action,args,context):
  headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
  repo=args["repository"].strip("/")
  if len(repo.split("/"))!=2 or any(not p or p in {".",".."} for p in repo.split("/")): raise ValueError("Invalid repository.")
  if action=="issues.list":
   response=httpx.get(f"https://api.github.com/repos/{repo}/issues",params={"state":args.get("state","open"),"per_page":max(1,min(50,args.get("limit",10)))},headers=headers,timeout=15.0)
   response.raise_for_status()
   return [{"number":x["number"],"title":x["title"],"state":x["state"],"url":x["html_url"],"is_pull_request":"pull_request" in x} for x in response.json()]
  if action=="issues.create":
   title=args["title"].strip()
   if not title: raise ValueError("Issue title cannot be blank.")
   body=args.get("body","")
   key=context.get("idempotency_key")
   if key: body=(body+"

<!-- smart-bethg-idempotency:"+key+" -->")[:60000]
   response=httpx.post(f"https://api.github.com/repos/{repo}/issues",json={"title":title,"body":body},headers=headers,timeout=15.0)
   response.raise_for_status(); issue=response.json()
   return {"number":issue["number"],"title":issue["title"],"url":issue["html_url"]}
  raise ValueError("Unsupported GitHub action.")
 def _drive(self,token,action,args):
  if action!="files.search": raise ValueError("Unsupported Google Drive action.")
  query=args["query"].replace("\\","\\\\").replace("'","\\'")
  response=httpx.get("https://www.googleapis.com/drive/v3/files",params={"q":f"trashed = false and name contains '{query[:200]}'","pageSize":max(1,min(50,args.get("limit",10))),"fields":"files(id,name,mimeType,webViewLink,modifiedTime)","orderBy":"modifiedTime desc"},headers={"Authorization":"Bearer "+token},timeout=15.0)
  response.raise_for_status()
  return response.json().get("files",[])
 def _slack(self,token,action,args,context):
  if action!="messages.send": raise ValueError("Unsupported Slack action.")
  text=args["text"].strip()
  if not text or len(text)>40000: raise ValueError("Slack message length is invalid.")
  response=httpx.post("https://slack.com/api/chat.postMessage",json={"channel":args["channel"],"text":text},
      headers={"Authorization":"Bearer "+token},timeout=15.0)
  response.raise_for_status(); data=response.json()
  if not data.get("ok"): raise ValueError("Slack rejected the message.")
  return {"channel":data.get("channel"),"ts":data.get("ts"),"message_sent":True}
