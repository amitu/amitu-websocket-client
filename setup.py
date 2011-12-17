from setuptools import setup, find_packages

setup(
    name = "amitu-websocket-client",
    description = "Eventlet based websocket client",
    version = "0.1.0",
    author = 'Amit Upadhyay',
    author_email = "upadhyay@gmail.com",

    url = 'http://github.com/amitu/amitu-websocket-client/',
    license = 'BSD',

    namespace_packages = ["amitu"],
    packages = find_packages(),
)
