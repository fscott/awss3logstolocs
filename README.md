### aws s3 log time

This script grabs your s3 logs, finds IPs within them, and associates those IPs to locations as found in the GeoLite2 csv databases provided by MaxMind (http://www.maxmind.com). Licensed under the CC BY-SA 3.0 license (http://creativecommons.org/licenses/by-sa/3.0/).

A typical usage would be:

```bash
./awss3logtime.py -s3 example.com -nobots -today
```

Which would grab download today's logs from the s3 bucket at logs.example.com/root and place them in the ./root/ directory before parsing (ignoring apparent bots) and associating them to locations, if possible.

Run with -h for options.
