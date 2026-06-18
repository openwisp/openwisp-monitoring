class OpenWispControllerHeaderMiddleware:
    """
    Add the controller discovery header on every response in the local test app.

    The OpenWrt openwisp-config agent validates the base URL before
    registration and expects this header to be present.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Openwisp-Controller"] = "true"
        return response
