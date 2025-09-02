# chat/services/container.py
from typing import Any, Dict, Type, TypeVar, Union

T = TypeVar("T")


class ServiceContainer:
    """Simple dependency injection container for services"""

    def __init__(self):
        self._services: Dict[Union[str, Type], Any] = {}
        self._singletons: Dict[Union[str, Type], Any] = {}

    def register_singleton(self, interface: Union[str, Type], implementation: Any):
        """Register a singleton service"""
        self._singletons[interface] = implementation

    def register(self, interface: Union[str, Type], implementation: Any):
        """Register a service (new instance each time)"""
        self._services[interface] = implementation

    def get(self, interface: Union[str, Type[T]]) -> T:
        """Get a service instance"""
        # Check singletons first
        if interface in self._singletons:
            return self._singletons[interface]

        # Check regular services
        if interface in self._services:
            service_class = self._services[interface]
            if callable(service_class):
                return service_class()
            return service_class

        raise ValueError(f"Service not registered: {interface}")

    def has(self, interface: Union[str, Type]) -> bool:
        """Check if a service is registered"""
        return interface in self._services or interface in self._singletons


# Global container instance
container = ServiceContainer()


def get_container() -> ServiceContainer:
    """Get the global service container"""
    return container
