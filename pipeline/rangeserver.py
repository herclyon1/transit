#!/usr/bin/env python3
"""本地预览用的静态服务器，支持 HTTP Range（pmtiles 必需；python -m http.server 不支持）。
   python3 pipeline/rangeserver.py 8788   → http://127.0.0.1:8788/"""
import http.server, os, re, sys
class H(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path=self.translate_path(self.path)
        rng=self.headers.get('Range')
        if not rng or not os.path.isfile(path): return super().send_head()
        m=re.match(r'bytes=(\d*)-(\d*)',rng); size=os.path.getsize(path)
        a=int(m.group(1)) if m.group(1) else max(0,size-int(m.group(2))); b=int(m.group(2)) if m.group(2) and m.group(1) else size-1
        b=min(b,size-1); f=open(path,'rb'); f.seek(a)
        self.send_response(206); self.send_header('Content-Type',self.guess_type(path)); self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Range',f'bytes {a}-{b}/{size}'); self.send_header('Content-Length',str(b-a+1)); self.end_headers()
        self.range=(a,b); return f
    def copyfile(self,src,dst):
        if hasattr(self,'range') and self.range: a,b=self.range; self.range=None; dst.write(src.read(b-a+1))
        else: super().copyfile(src,dst)
    def end_headers(self):
        self.send_header('Accept-Ranges','bytes'); super().end_headers()
    def do_POST(self):
        # ui/accept.js 把验收结果 POST 到 /accept → 写 .accept/<page>.json（pipeline/ui/accept.py 读）
        if self.path!='/accept': self.send_error(404); return
        import json; n=int(self.headers.get('Content-Length') or 0); d=json.loads(self.rfile.read(n) or b'{}')
        os.makedirs('.accept',exist_ok=True); name=(d.get('page','') or '').strip('/'); name=(name[:-10] if name.endswith('index.html') else name).strip('/').replace('/','_') or 'index'
        open(os.path.join('.accept',name+'.json'),'w').write(json.dumps(d,ensure_ascii=False,indent=1))
        self.send_response(204); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
    def log_message(self,*a): pass
http.server.ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1]) if len(sys.argv)>1 else 8788),H).serve_forever()
