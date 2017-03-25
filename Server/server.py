#!/usr/bin/env python

import os
import tornado.ioloop
import tornado.web
import tornado.escape
from tornado.options import define, options

import json
import maploader


define("port", default=8000, help="run on the given port", type=int)


class Application(tornado.web.Application):

    def __init__(self):
        handlers = [
            (r"/level/([A-Za-z0-9_-]+)", LevelHandler),
        ]
        super(Application, self).__init__(handlers, static_path="static",
                                          compress_response=True)


class LevelHandler(tornado.web.RequestHandler):
    def get(self, levelname):
        level = maploader.load_map(levelname)
        answer = json.dumps(level)
        self.set_header('Content-Type', 'application/json')
        self.write(answer)


def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    print "Listening on port %d" % (options.port,)
    os.system("ifconfig | grep inet")
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    main()
