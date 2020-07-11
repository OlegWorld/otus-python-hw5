import os
import re
import datetime
import mimetypes
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
from socket import *


OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
NOT_ALLOWED = 405


class HTTPResponse:
    reply_values = {
        OK: 'OK',
        FORBIDDEN: 'Forbidden',
        NOT_FOUND: 'Not Found',
        NOT_ALLOWED: 'Method Not Allowed'
    }

    def __init__(self, **kwargs):
        self.result = kwargs

    def create_response(self):
        response = 'HTTP/1.1 {} {}\r\n'.format(self.result['code'], self.reply_values[self.result['code']])
        response += 'Date: {}\r\n'.format(datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S'))
        response += 'Server: pseudo_http\r\n'
        response += 'Allow: GET, HEAD\r\n'
        response += 'Content-Length: {}\r\n'.format(len(self.result['data']) if 'data' in self.result else 0)
        if 'type' in self.result:
            response += 'Content-Type: {}\r\n'.format(self.result['type'])
        response += '\r\n'

        if self.result.get('request') and self.result.get('request') == 'GET':
            response = response.encode() + self.result.get('data', b'')
        else:
            response = response.encode()

        return response


class HTTPServer:
    def __init__(self, url='', port=8086, max_threads=4, max_connections=4):
        self.__socket = socket(AF_INET, SOCK_STREAM)
        self.__socket.bind((url, port))
        self.__executor = None
        self.__max_threads = max_threads
        self.__max_connections = max_connections
        self.__is_working = False

    def serve_forever(self):
        print('starting pseudo http server at {}'.format(self.__socket.getsockname()))
        self.__is_working = True
        self.__executor = ThreadPoolExecutor(self.__max_threads)
        self.__socket.listen(self.__max_connections)
        while self.__is_working:
            session, address = self.__socket.accept()
            self.__executor.submit(self.__handle_request, session)

    def stop(self):
        self.__is_working = False
        self.__executor.shutdown()
        self.__socket.close()
        print()
        print('pseudo http server stopped')

    def __handle_request(self, session):
        try:
            request = session.recv(1024)
            if request:
                self.__executor.submit(self.__create_response, session, request)
        except Exception as e:
            print('Request handle error: ', e)
            session.close()

    def __create_response(self, session, request):
        result = self.__parse_request(request)
        response = result.create_response()
        self.__executor.submit(self.__send_response, session, response)

    @staticmethod
    def __send_response(session, response):
        try:
            session.send(response)
            session.close()
        except Exception as e:
            print('Session error: ', e)
            session.close()

    def __parse_request(self, request):
        request = [s for s in request.decode().split('\r\n') if s]
        match = re.match(r'([A-Z]*) \/([a-zA-Z0-9\/\_\-\.\%\?\=\&]*) HTTP/[0-9\.]', request[0])
        if match:
            request_type, url = match.groups()
            path = unquote(urlparse(url).path)
            if request_type not in ('GET', 'HEAD'):
                return HTTPResponse(code=NOT_ALLOWED)

            return self.__process_request(request_type, path)
        else:
            return HTTPResponse(code=FORBIDDEN)

    def __process_request(self, request, path):
        if not os.path.exists(path):
            return HTTPResponse(code=NOT_FOUND)

        if not os.path.abspath(path).startswith(os.path.abspath(os.path.curdir)) or not os.access(path, mode=os.R_OK):
            return HTTPResponse(code=FORBIDDEN)

        if os.path.isdir(path):
            index = path + 'index.html'
            if os.path.exists(index):
                return HTTPResponse(request=request, code=OK, **self.__read_file(path + 'index.html'))
            else:
                return HTTPResponse(code=NOT_FOUND)

        return HTTPResponse(request=request, code=OK, **self.__read_file(path))

    @staticmethod
    def __read_file(path):
        with open(path, 'rb') as file:
            return {'data': file.read(), 'type': mimetypes.guess_type(path)[0]}


def main():
    server = HTTPServer()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    main()
