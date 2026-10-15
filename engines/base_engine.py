from abc import ABC, abstractmethod
import logging

class BaseEngine(ABC):
    """
    Clase base abstracta para todos los motores de extracción (Vectors).
    Implementa el Patrón Strategy para la ejecución de los escaneos.
    """
    def __init__(self, config: dict, http, storage, notifier=None):
        self.config = config
        self.http = http
        self.storage = storage
        self.notifier = notifier
        self.logger = logging.getLogger(f"arbitraje.{self.__class__.__name__.lower()}")

    @abstractmethod
    async def run(self):
        """Método principal que debe implementar cada motor."""
        pass
