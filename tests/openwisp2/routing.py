from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from openwisp_notifications.websockets.routing import get_routes

application = ProtocolTypeRouter(
    {'websocket': AuthMiddlewareStack(URLRouter(get_routes()))}
)
