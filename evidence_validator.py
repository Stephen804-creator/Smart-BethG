class EvidenceValidator:
 def validate(self,answer,evidence): return {"valid":True,"evidence_count":len(evidence or [])}
