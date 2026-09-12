from abc import ABC,abstractmethod
class ProviderBase(ABC):
 name="base"
 @abstractmethod
 def generate(self,messages,model,**kwargs): ...
