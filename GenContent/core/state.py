"""
Shared state across all routers
"""
from typing import Dict, Any

# Global storage for uploaded CSV data
uploaded_data: Dict[str, Any] = {}
