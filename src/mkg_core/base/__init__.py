"""Base Classes für die Anwendung.

Dieses Modul stellt abstrakte Basisklassen bereit:
    - BaseHandler: Basis für Lambda-Handler mit Error-Handling
    - BaseRepository: Interface für Datenzugriff (Repository Pattern)
    - BaseService: Basis für Business-Logik Services
"""

from mkg_core.base.handler import BaseHandler
from mkg_core.base.repository import BaseRepository
from mkg_core.base.service import BaseService

__all__ = [
    "BaseHandler",
    "BaseRepository",
    "BaseService",
]
