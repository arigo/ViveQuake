#!/usr/bin/env python

import os
import tornado.ioloop
import tornado.web
import tornado.escape
from tornado.options import define, options

import json
import maploader
import quakelib


define("port", default=8000, help="run on the given port", type=int)


class Application(tornado.web.Application):

    def __init__(self):
        handlers = [
            (r"/hello", HelloHandler),
            (r"/level/([A-Za-z0-9_-]+)", LevelHandler),
        ]
        super(Application, self).__init__(handlers, static_path="static",
                                          compress_response=True)
        self.srv = quakelib.QuakeServer(["+map", "e1m1"])
        self.periodic_callback = tornado.ioloop.PeriodicCallback(
            self.invoke_periodic_callback, 100)     # 10 per second
        self.periodic_callback.start()

    def invoke_periodic_callback(self):
        self.srv.host_frame()


class HelloHandler(tornado.web.RequestHandler):
    def get(self):
        level_name = app.srv.get_level_model_name()
        start_pos = app.srv.get_player_start_position()
        response = {
            'level': level_name,
            'start_pos': maploader.map_vertex(start_pos),
        }
        answer = json.dumps(response)
        self.set_header('Content-Type', 'application/json')
        self.write(answer)


class LevelHandler(tornado.web.RequestHandler):
    def get(self, levelname):
        level = maploader.load_map(levelname)
        answer = json.dumps(level)
        self.set_header('Content-Type', 'application/json')
        self.write(answer)


def main():
    global app
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    print "Listening on port %d" % (options.port,)
    os.system("ifconfig | grep inet")
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    main()
