# Type stubs for Outlines (to silence VS Code import warnings)
# This is NOT the actual library - just type hints for development

from typing import Any, Dict, Optional

class models:
    @staticmethod
    def Transformers(model: Any, tokenizer: Any) -> Any: ...

class generate:
    @staticmethod
    def json(model: Any, schema: Dict[str, Any]) -> Any: ...
