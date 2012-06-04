import sys
import json
import csv
from common import *

pony_list = [
    (
        (wikia_name or primary_name).decode('utf8').encode('ascii', 'xmlcharrefreplace'),
        dict(
            name=(wikia_name or primary_name).decode('utf8').encode('ascii', 'xmlcharrefreplace'),
            primary_name=primary_name.decode('utf8').encode('ascii', 'xmlcharrefreplace'),
            wikia_name=wikia_name.decode('utf8').encode('ascii', 'xmlcharrefreplace'),
            tags=tag_names.split(),
            pony_tags=pony_tag_names.split(),
            gender=gender,
            kind=kind,
            comments=comments.strip(),
            category=category,
        )
    )
    for primary_name, wikia_name, tag_names, pony_tag_names, gender, kind, comments, category
    in list(csv.reader(open('tmp/pony_list_wip.csv')))[1:]
    if wikia_name
]#[:6]
pony_dict = dict(pony_list)

genders = set([pony['gender'] for name, pony in pony_list])
kinds = set([pony['kind'] for name, pony in pony_list])

sites = dict(
    e621net=e621(alias_check=True),
    #rule34it=rule34it(), #down?
    wildcrittersws=wildcritters(alias_check=True),
    #wildcrittersnet=wildcrittersnet(), #has nothing?
    rule34xxx=rule34(alias_check=True),
    ponibooru=ponibooru(alias_check=True),
    paheal=paheal(alias_check=True),
)
site_list = sites.values()

#sites that don't use an _(mlp) suffix on their tags
#so there's room for horrible namespace clash
bad_tag_sites = set(['ponibooru', 'rule34xxx', 'rule34it', 'paheal'])

#some tags do have clash, and have been removed from the main list and added to a special column
pony_tag_sites = set(['ponibooru'])

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

if 'crawl' in sys.argv:
    key = sys.argv[-1]
    site = sites[key]
    results = {}
    try:
        for pony_name, pony in pony_list:
            print pony_name
            results[pony_name] = {}
            for tag in pony['tags']:
                if '_(mlp)' not in tag and key not in bad_tag_sites:
                    continue
                print '->', tag
                results[pony_name][tag] = site.crawl(tag)
                
            if key in pony_tag_sites:
                for tag in pony['pony_tags']:
                    print '->', tag
                    results[pony_name][tag] = site.crawl(tag)
            print
    finally:
        json.dump(results, open('tmp/mlp.%s.json' % site.__class__.__name__, 'w'))

if 'combine' in sys.argv:
    print "Loading"
    site_results = {}
    for site_name, site in sites.items():
        print '->', site_name
        site_results[site_name] = json.load(open('tmp/mlp.%s.json' % site.__class__.__name__))

    combined = {}
    site_counts = {}

    #these are just debug info
    site_tag_counts = {}
    site_md5s = {}
    print "Combining"
    for site_name in sites:
        site_tag_counts[site_name] = []
        site_md5s[site_name] = set()


    for pony_name, pony in pony_list:
        print '', pony_name
        by_md5 = {}

        site_counts[pony_name] = dict(by_tag=dict())

        for site_name, site in sites.items():
            print '->', site_name,
            site_by_md5 = {}
            site_counts[pony_name]['by_tag'][site_name] = dict()
            #first combine all the tags for the site
            site_data = site_results[site_name][pony_name]

            for tag in site_data:
                for result in site_data[tag]:
                    site_by_md5[result['md5']] = result
                site_counts[pony_name]['by_tag'][site_name][tag] = len(site_data[tag])

            #then track some info
            site_counts[pony_name][site_name] = len(site_by_md5)
            site_md5s[site_name].update(set(site_by_md5))
            print site_counts[pony_name][site_name],
            
            #then combine into the total

            for result in site_by_md5.values():
                md5 = result['md5']
                site_md5s[site_name].add(md5)

                tags = set(result['tags'].lower().split())
                site_tag_counts[site_name].append(len(tags))

                if md5 in by_md5:
                    existing_tags, existing_sites = by_md5[md5]
                    existing_tags.update(tags)
                    existing_sites.add(site_name)
                else:
                    by_md5[md5] = tags, set([site_name])
            print

        combined[pony_name] = by_md5
        print ' =', len(combined[pony_name])
        print

    print 'Stats'
    site_stats = {}
    for site_name, site in sites.items():
        post_count = len(site_md5s[site_name])
        tag_count = float(sum(site_tag_counts[site_name]))/len(site_tag_counts[site_name])
        unique = len(site_md5s[site_name].difference(*[site_md5s[sn] for sn in sites if sn != site_name]))
        print '->', site_name, 'has', post_count, 'posts, with', unique, 'uniques and averaging', tag_count, 'tags'
        site_stats[site_name] = dict(post_count=post_count, tag_count=tag_count, unique=unique)

    print 'Saving'
    json.dump(dict(combined=combined, site_counts=site_counts, site_stats=site_stats), open('tmp/mlp.combined.json', 'w'), cls=SetEncoder)
    print '-> Complete'

if 'analyze' in sys.argv:
    print 'Loading'
    file_data = json.load(open('tmp/mlp.combined.json'))
    data = file_data['combined']
    
    counts_by_pony = {}
    graph_data = []
    swapped_graph_data = []

    #find the total score and store it in various places
    for pony_name, pony in pony_list:
        total_count = float(len(data[pony_name]))
        counts_by_pony[pony_name] = total_count
        graph_data.append([pony_name, total_count])
        swapped_graph_data.append([total_count, pony_name])


    #make an ordered version of the graph data
    ordered_graph_data = []
    reorderings = {}
    for i, (total_count, pony_name) in enumerate(sorted(swapped_graph_data, reverse=True)):
        reorderings[i] = pony_name
        ordered_graph_data.append([i, total_count])

    #Now that we have that, start building up rows for analysis!

    print 'Creating Rows'
    rows = []
    category_rows = {}
    delta_rows = []

    for pony_name, pony in pony_list:
        print '->', pony_name
        total_count = counts_by_pony[pony_name]

        row = pony.copy()
        row.update(
            total_count=total_count,
            ratios=analyze_ratios(data[pony_name]),
        )
        for site_name, site in sites.items():
            row[site_name] = file_data['site_counts'][pony_name][site_name]

        rows.append(row)
        category_rows.setdefault(pony['category'], [])
        category_rows[pony['category']].append(row)

    def countsort(rows):
        rows.sort(key=itemgetter('total_count'), reverse=True)
    
    countsort(rows)
    for v in category_rows.values():
        countsort(v)

    print "Creating breakdowns"
    #build the grouped breakdown info
    breakdowns = {}
    scale_max = 0
    for breakdown_key in ('gender', 'kind'):
        data_map = {}
        for row in rows:
            map_key = row[breakdown_key]
            data_map.setdefault(map_key, []).append(row['total_count'])

            scale_max = max(scale_max, row['total_count'])
        breakdowns[breakdown_key] = sorted([
            (median(scores), scores, map_key) for map_key, scores in data_map.items()
        ], reverse=True)

    print "Finding Pairings"
    #remap pairings
    result_ponies = {}
    for pony_name, pony in pony_list:
        if pony['category'] == 'groups':
            #these ruin the data
            continue
        for md5, (tags, site) in data[pony_name].items():
            result_ponies.setdefault(md5, []).append(pony_name)

    pair_counts = collections.Counter()
    triple_counts = collections.Counter()
    for md5, numbers in result_ponies.items():
        if len(numbers) > 1:
            pair_counts.update(itertools.combinations(sorted(numbers), 2))
        if len(numbers) > 2:
            triple_counts.update(itertools.combinations(sorted(numbers), 3))

    adjusted_pairs = collections.Counter()
    adjusted_triples = collections.Counter()
    for (first, second), count in pair_counts.items():
        count = float(count)
        adjusted_pairs[(first, second)] = count * (count / counts_by_pony[first]) * (count / counts_by_pony[second])

    for (first, second, third), count in triple_counts.items():
        count = float(count)
        adjusted_triples[(first, second, third)] = count * (count / counts_by_pony[first]) * (count / counts_by_pony[second]) * (count / counts_by_pony[third])


    top_pairs = []
    for (first, second), count in adjusted_pairs.most_common(25):
        top_pairs.append(dict(
            first=first,
            second=second,
            total_count=count,
            ratios=analyze_ratios(dict([
                (md5, data[first][md5])
                for md5, numbers in result_ponies.items()
                if first in numbers and second in numbers
            ]))
        ))

    top_triples = []
    for (first, second, third), count in adjusted_triples.most_common(25):
        top_triples.append(dict(
            first=first,
            second=second,
            third=third,
            total_count=count*100,
            ratios=analyze_ratios(dict([
                (md5, data[first][md5])
                for md5, numbers in result_ponies.items()
                if first in numbers and second in numbers and third in numbers
            ]))
        ))

    print 'Writing Data'
    json.dump(dict(
        rows=rows,
        category_rows=category_rows,
        
        breakdowns=breakdowns,
        scale_max=scale_max,
        
        graph_data = graph_data,
        ordered_graph_data = graph_data,
        reorderings = reorderings,

        site_counts = file_data['site_counts'],
        site_stats = file_data['site_stats'],
        
        top_pairs = top_pairs,
        top_triples = top_triples,

    ), open('tmp/mlp.analyzed.json', 'w'), cls=SetEncoder)


if 'html' in sys.argv:
    def url_for(row, key):
        if key in ('e621net', 'wildcrittersws'):
            #these sites have the concept of an "or" search, handily
            #but they do have a limit of how many you can 'or' together, so we need to filter a bit
            tags = [tag for tag in pony_dict[row['name']]['tags'] if '_(mlp)' in tag]
            if len(tags) > 5:
                tags = [tag for tag in tags if json_data['site_counts'][row['name']]['by_tag'][key][tag]]
            
            if len(tags) == 1:
                term = tags[0]
            else:
                term = ' '.join(['~%s' % tag for tag in tags])

        else:
            #the other sites do not have an "or" operator, so we have to just take the best tag
            tags = json_data['site_counts'][row['name']]['by_tag'][key]
            term = max([(l, t) for t, l in tags.items()])[1].encode('utf8')

        return sites[key].get_url(term)

    json_data = json.load(open('tmp/mlp.analyzed.json'))

    print 'Creating HTML'
    from jinja2 import Template, Environment, PackageLoader
    env = Environment(loader=PackageLoader(__name__, 'pony_templates'))
    for template_file in ('index', 'chart', 'charts', 'faq', 'breakdowns'):
        print "->", template_file
        with open('pony_html/%s.html' % template_file, 'w') as out:
            out.write(env.get_template('%s.template.html' % template_file).render(
                #data
                pony_dict=pony_dict,
                #functions
                url_for=url_for,
                min=min,max=max,quote=urllib.quote,top_25=top_25,
                #file data
                **json_data
            ))
    print 'Done'
