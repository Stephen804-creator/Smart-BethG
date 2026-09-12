class ResponseComposer:
 def compose(self,result,verification=None): return {"status":"completed" if result else "failed","result":result,"verification":verification}
