# Usually models are shared or imported from auth, but if we need a separate model, we can reference the auth one.
# For simplicity and preventing duplicate table creation errors, we will import it from auth.
from ..auth.model import User

__all__ = ["User"]
