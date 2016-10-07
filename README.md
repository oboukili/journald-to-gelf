# journald-to-gelf
Stream journald json events to a gelf endpoint.
Supports sending via tcp,udp,tls protocols.

## Dependencies

* [pygelf](https://pypi.python.org/pypi/pygelf)

## Usage
#### Mandatory
* **[-s|--server]** : gelf endpoint address (*default: localhost*)

#### Optional
* **[-e|--environment]** : GELF *environment* optional message field to append to before sending (*default: None*).
* **[-f|--filters]** : journald comma-separated filters (*default: None*). If specified, will send to gelf endpoint only if there's a match with least one of the fields' value among 'SYSLOG_IDENTIFIER', 'SYSTEMD_UNIT' and 'UNIT'.
* **[-p|--port]** : gelf endpoint port (*default: 12201*)
* **[-t|--transportprotocol]** : gelf endpoint protocol (*default: udp, choices: [udp,tcp,tls]*)


## Examples

```journalctl -o json -f -t audit| journald-to-gelf.py -s mygelfendpoint```

```journalctl -o json -f | journald-to-gelf.py -s 10.0.0.1 -p 10999 -f postgresql,pg_ctl```

```journalctl -o json -f -u libvirtd | journald-to-gelf.py -s mygelfendpoint -e staging```
