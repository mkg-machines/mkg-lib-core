"""MKG Platform Core Library.

Gemeinsame Python-Kernbibliothek für die MKG Platform.
Stellt Base Classes, Pydantic Models, Exception-Hierarchie,
Utilities und AWS Client Wrapper bereit.

Modules:
    base: BaseHandler, BaseRepository, BaseService
    models: Pydantic-Basismodelle mit Standard-Feldern
    exceptions: Einheitliche Exception-Hierarchie
    utils: Logging, Tenant-Context, Validation, Pagination
    clients: AWS Client Wrapper (DynamoDB, S3, Secrets Manager)
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
