#!/usr/bin/env python

import sys
import os
import time
import json
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.escape
from tornado.options import define, options

import maploader
import quakelib


define("port", default=8000, help="run on the given port", type=int)


class Application(tornado.web.Application):

    def __init__(self):
        handlers = [
            (r"/hello", HelloHandler),
            (r"/level/([A-Za-z0-9_-]+)", LevelHandler),
            (r"/model/([A-Za-z0-9_:-]+)", ModelHandler),
            (r"/texture/([a-z0-9]+)", TextureHandler),
            (r"/snapshot", SnapshotHandler),
            (r"/websock", WebSockHandler),
        ]
        super(Application, self).__init__(handlers, static_path="static",
                                          compress_response=True)
        self.websocks = set()
        #
        if len(sys.argv) > 1:
            args = sys.argv[1:]
        else:
            args = ["+map", "e1m1"]
        self.srv = quakelib.QuakeServer(args)
        #
        self.periodic_callback = tornado.ioloop.PeriodicCallback(
            self.invoke_periodic_callback, 100)     # 10 per second
        self.periodic_callback.start()

    def invoke_periodic_callback(self):
        self.srv.host_frame()
        if self.websocks:
            snapshot = self.srv.get_snapshot()
            for ws in self.websocks:
                ws.write_message(snapshot)


def write_json_response(handler, response):
    answer = json.dumps(response)
    handler.set_header('Content-Type', 'application/json')
    handler.write(answer)


class HelloHandler(tornado.web.RequestHandler):
    def get(self):
        level_name = app.srv.get_level_model_name()
        start_pos = app.srv.get_player_start_position()
        response = {
            'level': level_name,
            'start_pos': maploader.map_vertex(start_pos),
            'palette': maploader.load_palette(),
        }
        write_json_response(self, response)

class LevelHandler(tornado.web.RequestHandler):
    def get(self, level_name):
        level = maploader.load_map(level_name)
        write_json_response(self, level)

class ModelHandler(tornado.web.RequestHandler):
    def get(self, model_name):
        if ':' not in model_name:
            model = maploader.load_model(model_name)
        else:
            level_name, model_index = model_name.split(':')
            model = maploader.load_map(level_name, int(model_index))
        write_json_response(self, model)

class TextureHandler(tornado.web.RequestHandler):
    def get(self, texture_name):
        image = maploader.load_texture(texture_name)
        write_json_response(self, image)

class SnapshotHandler(tornado.web.RequestHandler):
    def get(self):
        snapshot = app.srv.get_snapshot()
        print time.time()
        write_json_response(self, snapshot)

class WebSockHandler(tornado.websocket.WebSocketHandler):

    def open(self):
        print "opening websock"
        app.websocks.add(self)

    def on_close(self):
        app.websocks.discard(self)
        print "closed websock"


def main():
    global app
    #tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    print "Listening on port %d" % (options.port,)
    os.system("ifconfig | grep inet")
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    main()
