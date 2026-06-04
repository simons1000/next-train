#!/usr/bin/env python3
import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8090
HUXLEY = 'https://huxley2.azurewebsites.net'


def load_config():
    with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
        return json.load(f)


def build_departures_url(crs, via_crs='', filter_crs='', rows=None):
    url = f'{HUXLEY}/departures/{crs}'
    if via_crs:
        url += f'/to/{via_crs}'
    if filter_crs:
        url += f'/to/{filter_crs}'
    if rows is not None:
        url += f'/{rows}'
    return url


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def do_GET(self):
        if self.path == '/':
            self._file('index.html', 'text/html; charset=utf-8')

        elif self.path == '/api/departures':
            cfg        = load_config()
            crs        = cfg.get('station', 'WCP')
            token      = cfg.get('api_key', '')
            rows       = cfg.get('rows', 10)
            filter_crs = cfg.get('filter_crs', '')
            via_crs    = cfg.get('via_crs', '')

            url = build_departures_url(crs, via_crs=via_crs,
                                       filter_crs=filter_crs, rows=rows)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'next-train/1.0'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    url = build_departures_url(crs, via_crs=via_crs,
                                               filter_crs=filter_crs, rows=None)
                    try:
                        req = urllib.request.Request(url, headers={'User-Agent': 'next-train/1.0'})
                        with urllib.request.urlopen(req, timeout=10) as r:
                            data = r.read()
                    except urllib.error.HTTPError as e2:
                        self._json({'error': 'upstream_http', 'status': e2.code,
                                    'message': str(e2)}, 502)
                        return
                    except Exception as e2:
                        self._json({'error': 'upstream_error', 'message': str(e2)}, 502)
                        return
                else:
                    self._json({'error': 'upstream_http', 'status': e.code,
                                'message': str(e)}, 502)
                    return
            except Exception as e:
                self._json({'error': 'upstream_error', 'message': str(e)}, 502)
                return

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)

        else:
            self.send_error(404)

    def _file(self, path, content_type):
        try:
            with open(os.path.join(os.path.dirname(__file__), path), 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404)

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f'Serving on http://0.0.0.0:{PORT}')
    server.serve_forever()
