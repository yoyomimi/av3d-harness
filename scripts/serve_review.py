#!/usr/bin/env python3
"""Serve local review media with byte ranges for reliable native audio/video seeking."""
import argparse,functools,http.server,re,shutil
from pathlib import Path


class ReviewHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Accept-Ranges','bytes')
        if self.path.split('?',1)[0].endswith(('.html','.json')):self.send_header('Cache-Control','no-cache')
        super().end_headers()

    def send_head(self):
        self._remaining=None;value=self.headers.get('Range');path=Path(self.translate_path(self.path))
        if not value or not path.is_file():return super().send_head()
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',value.strip());size=path.stat().st_size
        if not match or not any(match.groups()):
            self.send_error(400,'One byte range required');return None
        lo,hi=match.groups()
        if lo:start=int(lo);end=min(int(hi),size-1) if hi else size-1
        else:start=max(0,size-int(hi));end=size-1
        if size==0 or start>=size or start>end:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return None
        try:source=path.open('rb')
        except OSError:self.send_error(404);return None
        source.seek(start);self._remaining=end-start+1
        self.send_response(206);self.send_header('Content-Type',self.guess_type(str(path)))
        self.send_header('Content-Range',f'bytes {start}-{end}/{size}');self.send_header('Content-Length',str(self._remaining))
        self.send_header('Last-Modified',self.date_time_string(path.stat().st_mtime));self.end_headers();return source

    def copyfile(self,source,outputfile):
        try:
            if self._remaining is None:shutil.copyfileobj(source,outputfile);return
            remaining=self._remaining
            while remaining:
                block=source.read(min(65536,remaining))
                if not block:break
                outputfile.write(block);remaining-=len(block)
        except (BrokenPipeError,ConnectionResetError):pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--port',type=int,default=8894);a=p.parse_args()
    handler=functools.partial(ReviewHandler,directory=str(a.directory.resolve()))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',a.port),handler);server.serve_forever()


if __name__=='__main__':main()
