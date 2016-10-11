#!/usr/bin/python
# coding: utf-8
#
# journald-to-gelf
# ============
#
# Dependencies:
# -------------
# - pygelf (pip-install pygelf)
#
# Heavily inspired from journal2gelf.
# https://github.com/joemiller
#
# Uses Mirec Miskuf's implementation on how to get string objects instead of Unicode one when calling
# http://stackoverflow.com/a/33571117/1709587
#
# Released under the MIT license, see LICENSE for details.

import sys,json,zlib,signal,re,argparse
from collections import deque
from pygelf import GelfUdpHandler,GelfTcpHandler,GelfTlsHandler

unfilteredJournalctlKeys = ['SYSLOG_IDENTIFIER', 'SYSTEMD_UNIT', 'UNIT']

def json_loads_byteified(json_text):
    return _byteify(
        json.loads(json_text, object_hook=_byteify),
        ignore_dicts=True
    )

def _byteify(data, ignore_dicts = False):
    if isinstance(data, unicode):
        return data.encode('utf-8')
    if isinstance(data, list):
        return [ _byteify(item, ignore_dicts=True) for item in data ]
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
            for key, value in data.iteritems()
        }
    return data

class StreamToGelf:

    def __init__(self, stream, host='localhost', port=12201, protocol='udp', _filters=None, environment=None, json_only=False):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        self.buffer = deque()
        self.environment = str(environment)
        if _filters is not None:
            self.filters = _filters.split(',')
        else:
            self.filters = None
        self.json_only = bool(json_only)
        self.protocol = str(protocol)
        self.stream = stream
        self.handleropts= {'host': str(host), 'port': int(port), 'protocol': str(protocol)}
        if str(protocol) == 'udp':
            self.gelfhandler = GelfUdpHandler(host=str(host), port=int(port),include_extra_fields=True, compress=True)
        elif str(protocol) == 'tcp':
            self.gelfhandler = GelfTcpHandler(host=str(host), port=int(port),include_extra_fields=True)
        elif str(protocol) == 'tls':
            self.gelfhandler = GelfTlsHandler(host=str(host), port=int(port),include_extra_fields=True)

    def _send_gelf(self):

        try:
            record = json_loads_byteified(''.join(self.buffer))
        except ValueError as e:
            print "ERROR - cannot load json: " + str(e)
        else:
            try:
                assert 'MESSAGE' in record.keys()
            except AssertionError:
                pass
            else:
                if self.filters is not None:
                    matchlist = [record[filterkey] for filterkey in record.keys() if filterkey in unfilteredJournalctlKeys]
                    for filterelement in self.filters:
                        for matchelement in matchlist:
                            if re.search(str(filterelement),str(matchelement)):
                                break
                        else:
                            continue
                        break

                message = {'version': '1.1'}
                for key, value in record.iteritems():
                    if key == 'MESSAGE':
                        # try to unnest and index json message keys, if the message is a valid json.
                        try:
                            innerrecord = json_loads_byteified(value)
                        except AttributeError:
                            if self.json_only:
                                break
                            else:
                                message['short_message'] = value
                        except ValueError:
                            if self.json_only:
                                break
                            else:
                                message['short_message'] = value
                        except Exception as e:
                            print (e)
                            break
                        else:
                            try:
                                assert 'message' in innerrecord.keys()
                            except AssertionError:
                                message['short_message'] = json.dumps(innerrecord)
                            else:
                                try:
                                    for hashkey, hashvalue in innerrecord.iteritems():
                                        if str(hashkey) == 'message':
                                            message['short_message'] = hashvalue
                                        else:
                                            message['_' + str(hashkey).lower()] = hashvalue
                                except Exception as e:
                                    print "EXCEPTION: " + str(e)
                    elif key == '__REALTIME_TIMESTAMP':
                        # convert from systemd's format of microseconds expressed as
                        # an integer to graylog's float format, eg: "seconds.microseconds"
                        message['timestamp'] = float(value) / (1000 * 1000)
                    elif key == '_HOSTNAME':
                        message['host'] = value
                    else:
                        if len(unfilteredJournalctlKeys) > 0 and str(key) in unfilteredJournalctlKeys:
                            message['_' + str(key).lower()] = value
                    if self.environment is not None:
                        message['_environment'] = str(self.environment)

                else:
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
        self.buffer.clear()
        self.gelfhandler.flush()
        self.gelfhandler.close()
        print "Exiting..."
        sys.exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--host', dest='host', default='localhost', type=str, help='Graylog2 host or IP', required=True)
    parser.add_argument('-p', '--port', dest='port', default=12201, type=int, help='Graylog2 input port')
    parser.add_argument('-t', '--transport-protocol', dest='transportprotocol', default='udp', type=str, choices=['udp','tcp','tls'],help='Graylog2 input protocol')
    parser.add_argument('-f', '--filters', dest='filters', type=str, default=None, help='Comma separated systemd syslog_identifier filter strings')
    parser.add_argument('-e', '--environment', dest='environment', type=str, default=None, help='Optional gelf message field "environment" to append to')
    parser.add_argument('-j', '--json-only', dest='json_only', action='store_true', default=False, help='Stream json formatted logs only')
    results = parser.parse_args()

    mystream = StreamToGelf(stream=sys.stdin, host=results.host, port=results.port, protocol=results.transportprotocol, _filters=results.filters, environment=results.environment, json_only=results.json_only)
    mystream.run()
