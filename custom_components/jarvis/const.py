"""Constants for the Jarvis conversation-agent integration."""

DOMAIN = "jarvis"

CONF_URL = "url"
CONF_DEFAULT_AREA = "default_area"

# Inside docker-compose the conductor is reachable by its service name.
DEFAULT_URL = "http://conductor:8000"
DEFAULT_AREA = "home"

# How long to wait on the conductor before speaking an error.
REQUEST_TIMEOUT_S = 30
