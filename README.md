# journald-to-gelf
Stream journald json events to a gelf endpoint.
Supports sending via tcp,udp,tls protocols.

## Dependencies

* [pygelf](https://pypi.python.org/pypi/pygelf)
  
## Usage
#### Mandatory
* **-s** : gelf endpoint address (*default: localhost*)
* **-p** : gelf endpoint port (*default: 12201*)
* **-t** : gelf endpoint protocol (*default: udp, choices: [udp,tcp,tls]*)

#### Optional
* **-f** : journald comma-separated filters (*default: None*). If specified, will send to gelf endpoint only if there's a match with least one of the fields' value among 'SYSLOG_IDENTIFIER', 'SYSTEMD_UNIT' and 'UNIT'.

## Examples

```journalctl -o json -f|journald-to-gelf.py -s mygelfendpoint -t tcp```

```journalctl -o json -f|journald-to-gelf.py -s 10.0.0.1 -p 10999 -f postgresql,pg_ctl```
