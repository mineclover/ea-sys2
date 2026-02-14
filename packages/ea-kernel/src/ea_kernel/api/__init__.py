
from pathlib import Path

from ea_kernel.schema_loader import load_kernel_schema_from_package

from .server import create_app

# Provide a ready-to-use app instance for `uvicorn ea_kernel.api:app --reload`
# We use a default data directory "data/governance_api"
default_data_dir = Path("data/governance_api")
schema = load_kernel_schema_from_package()

app = create_app(default_data_dir, schema)
