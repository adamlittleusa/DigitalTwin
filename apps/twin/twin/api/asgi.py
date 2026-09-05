"""The eager application uvicorn imports. This is the only module that reads the environment at import."""

from twin.api.app import create_app
from twin.config import load_env_file
from twin.wiring import load_runtime

load_env_file()
app = create_app(load_runtime())
