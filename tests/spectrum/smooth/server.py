#!/usr/bin/env python3
# Serves index.html + the 4K clip and logs the page's per-second rows. Phase is set by writing the phase file.
import http.server,sys,os,json
D=os.path.dirname(os.path.abspath(__file__)); OUT=sys.argv[1]; PH=sys.argv[2]
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=D,**k)
    def log_message(s,*a): pass
    def do_POST(s):
        b=s.rfile.read(int(s.headers['Content-Length'])).decode()
        with open(OUT,'a') as f: f.write(b+'\n')
        p=open(PH).read().strip() if os.path.exists(PH) else 'light'
        s.send_response(200); s.end_headers(); s.wfile.write(p.encode())
http.server.ThreadingHTTPServer(('127.0.0.1',18098),H).serve_forever()
