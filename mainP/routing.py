from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from channels.auth import AuthMiddlewareStack
from firstPage import consumer
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

websocket_path = [
    path("ws/pollData/", consumer.DashboardConsumer.as_asgi()), # type: ignore
    path("ws/voteData/", consumer.VoteConsumer.as_asgi()), # type: ignore
    path("ws/votes/", consumer.VoteConsumer2.as_asgi()), # type: ignore
]

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_path)
    ),
})