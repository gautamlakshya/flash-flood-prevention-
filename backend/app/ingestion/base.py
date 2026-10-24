from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

class ProviderStatus:
    CONNECTED = "CONNECTED"
    AVAILABLE_LOCALLY = "AVAILABLE LOCALLY"
    CONFIGURED = "CONFIGURED"
    RESTRICTED = "RESTRICTED"
    SIMULATED = "SIMULATED"
    NOT_CONFIGURED = "NOT CONFIGURED"
    ERROR = "ERROR"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class DataProvider(ABC):
    def __init__(self):
        self.source_name: str = "Unknown"
        self.source_type: str = "Unknown"
        self.last_updated: Optional[datetime] = None
        self.error_message: Optional[str] = None
    
    @abstractmethod
    def fetch_data(self, **kwargs) -> Any:
        """
        Fetches or loads the data based on the provider's implementation.
        Can return a list of dictionaries, a pandas DataFrame, or a rasterio dataset depending on the type.
        """
        pass
    
    @abstractmethod
    def get_status(self) -> str:
        """
        Returns one of the ProviderStatus constants.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """
        Returns metadata about the provider and its current state.
        """
        return {
            "name": self.source_name,
            "type": self.source_type,
            "status": self.get_status(),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "error": self.error_message
        }
