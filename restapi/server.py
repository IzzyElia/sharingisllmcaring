from . import handler
from . import api
from http.server import ThreadingHTTPServer

def start_server():
    for api_function in handler.APIFunction.__subclasses__():
        for endpoint in api_function.endpoints:
            handler.register_endpoint(endpoint, api_function)

    server = ThreadingHTTPServer(('localhost', 8080), handler.Handler)

    server.serve_forever()