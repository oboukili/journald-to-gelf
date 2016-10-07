#!/usr/bin/python
#
# json2gelf
# ============
#
# Dependencies:
# -------------
# - pygelf (pip-install pygelf)
#
# Heavily inspired from journal2gelf.
# https://github.com/joemiller
#
# Released under the MIT license, see LICENSE for details.

import sys,json,zlib,signal,re
from collections import deque
from pygelf import GelfUdpHandler,GelfTcpHandler,GelfTlsHandler

unfilteredJournalctlKeys = ['SYSLOG_IDENTIFIER', 'SYSTEMD_UNIT', 'UNIT']

class StreamToGelf:

    def __init__(self, stream, host='localhost', port=12201, protocol='udp', _filters=None, environment=None):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        self.buffer = deque()
        self.environment = environment
        if _filters is not None:
            self.filters = _filters.split(',')
        else:
            self.filters = None
        self.protocol = str(protocol)
        self.stream = stream
        self.handleropts = {'host': str(host), 'port': int(port), 'protocol': str(protocol)}
        if str(protocol) == 'udp':
            self.gelfhandler = GelfUdpHandler(host=str(host), port=int(port),include_extra_fields=True, compress=True)
        elif str(protocol) == 'tcp':
            self.gelfhandler = GelfTcpHandler(host=str(host), port=int(port),include_extra_fields=True)
        elif str(protocol) == 'tls':
            self.gelfhandler = GelfTlsHandler(host=str(host), port=int(port),include_extra_fields=True)

    def _send_gelf(self):
        message = {'version': '1.1'}
        try:
            record = json.loads(''.join(self.buffer))
            for key, value in record.iteritems():
                # journalctl's JSON exporter will convert unprintable (incl. newlines)
                # strings into an array of integers. We convert these integers into
                # their ascii representation and concatenate them together
                # to reconstitute the string.
                if isinstance(value,list):
                    value = ''.join([chr(x) for x in value])
                if key == '__REALTIME_TIMESTAMP':
                    # convert from systemd's format of microseconds expressed as
                    # an integer to graylog's float format, eg: "seconds.microseconds"
                    message['timestamp'] = float(value) / (1000 * 1000)
                elif key == 'PRIORITY':
                    message['level'] = int(value)
                elif key == '_HOSTNAME':
                    message['host'] = value
                elif key == 'MESSAGE':
                    message['short_message'] = value
                    # try to unnest and index json message keys, if the message is a valid json.
                    try:
                        myhash = json.loads(value)
                    except ValueError:
                        pass
                    else:
                        for hashkey, hashvalue in myhash.iteritems():
                            if hashkey == 'message':
                                message['short_message'] = hashvalue
                            else:
                                message['_' + str(hashkey).lower()]  = hashvalue
                else:
                    if len(unfilteredJournalctlKeys) > 0 and str(key) in unfilteredJournalctlKeys:
                        message['_' + str(key).lower()] = value
                if 'level' not in message.keys() and 'loglevel' not in message.keys():
                    message['loglevel'] = "notice"
        except ValueError as e:
            print "ERROR - cannot load json: " + str(e)
        else:
            if self.filters is not None:
                TO_SEND = False
                matchlist = [record[filterkey] for filterkey in [key for key in record.keys() if key in unfilteredJournalctlKeys]]
                for filterelement in self.filters:
                    for matchelement in matchlist:
                        if re.search(str(filterelement),str(matchelement)):
                            TO_SEND = True
            else:
                TO_SEND = True
            if TO_SEND:
                if self.environment is not None:
                    message['_environment'] = str(self.environment)
                try:
                    if self.protocol != 'udp':
                        self.gelfhandler.send(zlib.compress(json.dumps(message)))
                    else:
                        self.gelfhandler.send(json.dumps(message))
                except Exception as e:
                    print str(e)
        finally:
            self.buffer.clear()

    def run(self):
        for line in self.stream:
            line = line.strip()
            self.buffer.append(line)
            self._send_gelf()

    def stop(self,*args):
        self.gelfhandler.flush()
        self.gelfhandler.close()
        print "Exiting..."
        sys.exit(0)

if __name__ == '__main__':
    import optparse

    opts_parser = optparse.OptionParser()
    opts_parser.add_option('-s', '--host', dest='host', default='localhost', type='str',
                            help='Graylog2 host or IP (default: %default)')
    opts_parser.add_option('-p', '--port', dest='port', default=12201, type='int',
                            help='Graylog2 input port (default: %default)')
    opts_parser.add_option('-t', '--transport-protocol', dest='transportprotocol', default='udp', type='choice', choices=['udp','tcp','tls'],
                            help='Graylog2 input protocol (default: %default)')
    opts_parser.add_option('-f', '--filters', dest='filters', type='str', default=None,
                            help='Comma separated systemd syslog_identifier filter strings (default: %default)')
    opts_parser.add_option('-e', '--environment', dest='environment', type='str', default=None,
                            help='Optional gelf message field "environment" to append to (default: %default)')
    (opts, args) = opts_parser.parse_args()

    parser = StreamToGelf(stream=sys.stdin, host=opts.host, port=opts.port, protocol=opts.transportprotocol, _filters=opts.filters, environment=opts.environment)
    parser.run()
