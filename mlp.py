import sys
import json

if 'parse_ponies' in sys.argv:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(open('tmp/List_of_ponies.htm'))
    rows = soup.select(".listofponies tr")
    ponies = {}
    for row in rows:
        tds = row('td')
        if len(tds) <= 7 or 'id' not in tds[0].attrs:
            continue
        ponies[tds[0]['id']] = dict(
            name = tds[0].text,
            kind = tds[1].text,
            group = tds[2].text,
            appeared_at = [i for i in tds[6] if isinstance(i, basestring)],
        )

    json.dump(ponies, open('tmp/pony_list.json', 'w'), indent=1)

if 'to_csv' in sys.argv:
    import csv, cStringIO, codecs
    class UnicodeWriter:
        """
        A CSV writer which will write rows to CSV file "f",
        which is encoded in the given encoding.
        """

        def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
            # Redirect output to a queue
            self.queue = cStringIO.StringIO()
            self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
            self.stream = f
            self.encoder = codecs.getincrementalencoder(encoding)()

        def writerow(self, row):
            self.writer.writerow([s.encode("utf-8") for s in row])
            # Fetch UTF-8 output from the queue ...
            data = self.queue.getvalue()
            data = data.decode("utf-8")
            # ... and reencode it into the target encoding
            data = self.encoder.encode(data)
            # write to the target stream
            self.stream.write(data)
            # empty queue
            self.queue.truncate(0)

        def writerows(self, rows):
            for row in rows:
                self.writerow(row)

    d = json.load(open('tmp/pony_list.json'))
    w = UnicodeWriter(open('tmp/pony_list.csv', 'w'), lineterminator='\n')

    s = sorted(d.items())
    w.writerow(['primary name', 'wikia names', 'space-seperated list of tag names', 'group', 'kind', 'appearance time'])
    for a, b in s:
        w.writerow([a, b['name'], '', b['group'], b['kind']] + b['appeared_at'])
