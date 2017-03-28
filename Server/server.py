#!/usr/bin/env python

import sys
import os
import time
import json
import cStringIO
import struct
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.escape
from tornado.options import define, options
from tornado.log import enable_pretty_logging

import maploader
import quakelib


define("port", default=8000, help="run on the given port", type=int)


class Application(tornado.web.Application):

    def __init__(self):
        handlers = [
            (r"/hello", HelloHandler),
            (r"/level/([A-Za-z0-9_-]+)", LevelHandler),
            (r"/model/([A-Za-z0-9_,-]+)", ModelHandler),
            (r"/texture/([a-z0-9]+)", TextureHandler),
            (r"/websock/2", WebSockHandler),
        ]
        super(Application, self).__init__(handlers, static_path="static",
                                          compress_response=True)
        self.clients = {}
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
        if self.clients:
            snapshot = self.srv.get_snapshot()
            for client in self.clients.values():
                client.update_snapshot(snapshot)


def write_json_response(handler, response):
    answer = json.dumps(response)
    handler.set_header('Content-Type', 'application/json')
    handler.write(answer)


class HelloHandler(tornado.web.RequestHandler):
    def get(self):
        level_name = app.srv.get_level_model_name()
        start_pos = app.srv.get_player_start_position()
        response = {
            'version': maploader.VERSION,
            'level': level_name,
            'start_pos': maploader.map_vertex(start_pos),
            'lightstyles': app.srv.get_lightstyles(),
        }
        write_json_response(self, response)

class LevelHandler(tornado.web.RequestHandler):
    def get(self, level_name):
        level = maploader.load_level(level_name)
        write_json_response(self, level)

class ModelHandler(tornado.web.RequestHandler):
    def get(self, model_name):
        if ',' not in model_name:
            model = maploader.load_model(model_name)
        else:
            level_name, model_index = model_name.split(',')
            model = maploader.load_bsp(level_name, int(model_index))
        write_json_response(self, model)

class TextureHandler(tornado.web.RequestHandler):
    def get(self, texture_name):
        image = maploader.load_texture(texture_name)
        write_json_response(self, image)

class WebSockHandler(tornado.websocket.WebSocketHandler):

    def open(self):
        print "opening websock"
        app.clients[self] = Client(self)

    def on_close(self):
        client = app.clients.pop(self)
        client.close()
        print "closed websock"


class Client(object):
    def __init__(self, ws):
        self.ws = ws
        self.prev_snapshot = []

    def update_snapshot(self, snapshot):
        # Compress a list containing floats and strings, based on the
        # previous-sent list.  Strings are supposed to change rarely.
        # The compression sends just one bit for every item in the list
        # that was not modified.
        #
        snapshot += [0.0] * ((-len(snapshot)) & 7)
        prev_snapshot = self.prev_snapshot
        if len(prev_snapshot) < len(snapshot):
            prev_snapshot += [0.0] * (len(snapshot) - len(prev_snapshot))
        #
        f = cStringIO.StringIO()
        header, header_bits, block = 0, 0, ""
        #
        for prev, entry in zip(prev_snapshot, snapshot):
            if entry != prev:
                header |= (1 << header_bits)
                if isinstance(entry, str):
                    nan_header = "\xff\xc0"
                    block += nan_header + chr(len(entry)) + entry
                else:
                    if entry != entry:     # NaN?
                        entry = 0.0
                    block += struct.pack("!f", entry)
            header_bits += 1
            if header_bits == 8:
                f.write(chr(header) + block)
                header, header_bits, block = 0, 0, ""
        #
        assert header_bits == 0
        self.prev_snapshot = snapshot
        #
        self.ws.write_message(f.getvalue())

    def close(self):
        pass


def main():
    global app
    enable_pretty_logging()
    #tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    print "Listening on port %d" % (options.port,)
    os.system("ifconfig | grep inet")
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    main()
