"""Owner-scoped connector installations and trusted adapter registry.
Only secret-manager references belong here; never store provider tokens in this table.
External adapters must be registered by trusted application code.
"""
import json
from database import get_connection
from services.capability_registry import CapabilityRegistry

CATALOG = {
 "github":{"name":"GitHub","category":"development","auth":"oauth_or_secret_ref"},
 "google_drive":{"name":"Google Drive","category":"storage","auth":"oauth_or_secret_ref"},
 "slack":{"name":"Slack","category":"communication","auth":"oauth_or_secret_ref"},
 "smartbethg":{"name":"Smart BethG Knowledge","category":"internal","auth":"session"},
}

class _KnowledgeSearchAdapter:
    def execute(self, action, arguments, context):
        if action != "knowledge.search":
            return {"success":False,"status":"unsupported"}
        from services.knowledge_service import KnowledgeService
        results = KnowledgeService().search(context["user_id"], arguments["query"],
                                            top_k=max(1,min(10,int(arguments.get("limit",3)))))
        return {"success":True,"status":"completed","results":results}

class ConnectorRegistry:
    def __init__(self, capabilities=None):
        self.capabilities = capabilities or CapabilityRegistry()
        self._adapters = {"smartbethg":_KnowledgeSearchAdapter()}
    def register_adapter(self, connector_key, adapter):
        if connector_key not in CATALOG:
            raise ValueError("Connector is not in the trusted catalog.")
        if not callable(getattr(adapter,"execute",None)):
            raise ValueError("Adapter must implement execute(action, arguments, context).")
        if connector_key in self._adapters:
            raise ValueError("An adapter is already registered.")
        self._adapters[connector_key] = adapter
    def adapter(self, connector_key):
        return self._adapters.get(connector_key)
    def catalog(self):
        return [{"key":key,**metadata,"actions":self.capabilities.list_for_connector(key),
                 "adapter_available":key in self._adapters} for key,metadata in CATALOG.items()]

class ConnectorInstallationService:
    def list_for_user(self, user_id):
        conn=get_connection()
        try:
            rows=conn.execute("SELECT id,user_id,connector_key,label,status,credential_ref,granted_permissions_json,created_at,updated_at FROM connector_installations WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall()
            return [self._decode(row) for row in rows]
        finally: conn.close()
    def get_for_user(self, user_id, installation_id):
        conn=get_connection()
        try:
            row=conn.execute("SELECT id,user_id,connector_key,label,status,credential_ref,granted_permissions_json,created_at,updated_at FROM connector_installations WHERE id=? AND user_id=? LIMIT 1",(installation_id,user_id)).fetchone()
            return self._decode(row) if row else None
        finally: conn.close()
    def install(self, user_id, connector_key, label=None, permissions=None):
        if connector_key not in CATALOG:
            raise ValueError("Unknown connector. Choose one from the trusted catalog.")
        permissions = permissions if permissions is not None else (["smartbethg.knowledge.search"] if connector_key=="smartbethg" else [])
        if not isinstance(permissions,list) or len(permissions)>30:
            raise ValueError("Permissions must be a list of at most 30 actions.")
        allowed={item["permission"] for item in CapabilityRegistry().list_for_connector(connector_key)}
        if any(item not in allowed for item in permissions):
            raise ValueError("A requested permission is not defined for this connector.")
        label=(label or CATALOG[connector_key]["name"]).strip()
        if not label or len(label)>120: raise ValueError("Connector label must be between 1 and 120 characters.")
        conn=get_connection()
        try:
            conn.execute("INSERT INTO connector_installations(user_id,connector_key,label,status,granted_permissions_json) VALUES (?,?,?,'disconnected',?) ON CONFLICT(user_id,connector_key,label) DO NOTHING",(user_id,connector_key,label,json.dumps(sorted(set(permissions)))))
            conn.commit()
        finally: conn.close()
        return next(item for item in self.list_for_user(user_id) if item["connector_key"]==connector_key and item["label"]==label)
    def disconnect(self,user_id,installation_id):
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE connector_installations SET status='disconnected',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(installation_id,user_id))
            conn.commit()
            return cursor.rowcount==1
        finally: conn.close()
    @staticmethod
    def _decode(row):
        item=dict(row)
        try: item["granted_permissions"]=json.loads(item.pop("granted_permissions_json") or "[]")
        except (TypeError,json.JSONDecodeError):
            item["granted_permissions"]=[]; item.pop("granted_permissions_json",None)
        item.pop("credential_ref",None)
        return item
