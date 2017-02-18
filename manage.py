#!/usr/bin/env python
from flask_script import Manager, Shell, Server
from ludmin import create_app

manager = Manager(create_app)

manager.add_command(
    'runserver',
    Server(host='0.0.0.0', port=8080)
)

if __name__ == '__main__':
    manager.run()
