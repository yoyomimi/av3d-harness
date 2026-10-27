#!/usr/bin/env python3
"""Receive one browser canvas recording on loopback; never overwrite a capture."""
import argparse
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--origin',default='http://127.0.0.1:8894');a=p.parse_args()
class Handler(BaseHTTPRequestHandler):
 def respond(self,code):
  self.send_response(code);self.send_header('Access-Control-Allow-Origin',a.origin);self.send_header('Access-Control-Allow-Methods','POST,OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers()
 def do_OPTIONS(self):self.respond(204)
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'))
  if self.headers.get('Origin')!=a.origin or self.path!='/save' or not 0<n<150000000 or a.output.exists():self.respond(409);return
  data=self.rfile.read(n)
  if len(data)!=n:self.respond(400);return
  with a.output.open('xb') as f:f.write(data)
  self.respond(200);self.wfile.write(b'Saved to project')
HTTPServer(('127.0.0.1',8895),Handler).serve_forever()
