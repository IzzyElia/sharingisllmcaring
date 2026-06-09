from . import handler
from http.server import ThreadingHTTPServer



# API module imports for APIFunction.subclasses discovery

from . import api

# ------------------------------------------------

def get_subclasses_recursive(super_class):
    for subclass in super_class.__subclasses__():
        yield subclass
        yield from get_subclasses_recursive(subclass)

def start_server():
    for api_function in get_subclasses_recursive(handler.APIFunction):
        instance = api_function()
        for endpoint in instance.endpoints():
            handler.register_endpoint(endpoint, instance)

    server = ThreadingHTTPServer(('localhost', 8080), handler.Handler)
    print('Server started at http://localhost:8080')
    server.serve_forever()