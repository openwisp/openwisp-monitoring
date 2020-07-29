from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from openwisp_notifications.websockets.routing import get_routes

from openwisp_controller.geo.channels.routing import geo_routes

application = ProtocolTypeRouter(
    {
        'websocket': AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(get_routes() + geo_routes))
        )
    }
)
