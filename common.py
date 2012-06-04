import urllib
import urllib2
import requests
import json
import cookielib
import xml.dom.minidom
from operator import itemgetter
import itertools
import collections
import re
import time
    
class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def median(values):
    v = sorted(values)
    l = len(v)-1
    half = l/2
    if l % 2:
        return v[half]
    if l == 1:
        return v[0]
    if not l:
        if v:
            return v[0]
        return 0
    return (v[half]+v[half+1])/2


class site(object):
    translations = {
        'nidoranf': 'nidoran%E2%99%80',
        'nidoranm': 'nidoran%E2%99%82',
        'hooh': 'ho-oh',
        'farfetchd': "farfetch'd",
        'mrmime': 'mr._mime',
        'mimejr': 'mime_jr.',
        'porygonz': 'porygon-z',
    }
    def __init__(self, alias_check=False):
        self.pokemon_counts = {}
        self.total_count = 0
        self.alias_check = alias_check

    def translate(self, term):
        #Turn a name into a URL term
        #and fixup any site-specific peculiarities
        if term in self.translations:
            return self.translations[term]
        return urllib2.quote(term)

    def get_url(self, term):
        return self.url % self.translate(term)

    def get_api_url(self, term, page):
        return self.api_url % (self.translate(term), page)

    def crawl(self, term):
        rows = []
        page = 0
        while True:
            page += 1
            data = urllib2.urlopen(self.get_api_url(term, page)).read()
            data = json.loads(data)
            if self.alias_check and page == 1:
                #check that we're not on an alias
                found = False
                for row in data:
                    if term in row['tags'].lower().split():
                        found = True
                        break
                if not found:
                    print "Skipping due to alias detected"
                    return []

            rows.extend(data)
            if len(data) < 100:
                #incomplete page means the last page
                break
        return rows




class e621(site):
    api_url = 'http://e621.net/post/index.json?tags=%s+-rating:safe&limit=100&page=%i'
    url = 'http://e621.net/post?tags=%s+-rating:safe'

class wildcritters(site):
    api_url = 'http://wildcritters.ws/post/index.json?tags=%s+-rating:safe&limit=100&page=%i'
    url = 'http://wildcritters.ws/post?tags=%s+-rating:safe'

class wildcrittersnet(site):
    api_url = 'http://wildcritters.net/wc/post/index.json?tags=%s+-rating:safe&limit=100&page=%i'
    url = 'http://wildcritters.net/wc/post?tags=%s+-rating:safe'

class rule34it(site):
    api_url = 'http://rule34.it/post/index.json?tags=%s+-rating:safe&limit=100&page=%i'
    url = 'http://rule34.it/post?tags=%s+-rating:safe'

class rule34(site):
    api_url = 'http://rule34.xxx/index.php?page=dapi&s=post&q=index&tags=%s&pid=%i'
    url = 'http://rule34.xxx/index.php?page=post&s=list&tags=%s'

    def crawl(self, term):
        rows = []
        page = -1 #start page is 0, not 1!
        tag_set = set()
        while True:
            page += 1
            data = urllib2.urlopen(self.get_api_url(term, page)).read()
            #and it doesn't escape special characters very well either
            data = xml.dom.minidom.parseString(data)
            data = data.getElementsByTagName('post')
            for post in data:
                row = { name:attr.value for (name,attr) in post._attrs.items() }
                tag_set.update(row['tags'].lower().split())
                rows.append(row)
            if len(data) < 100:
                #incomplete page means the last page
                break
        if self.alias_check and term not in tag_set:
            #we hit a tag alias
            #those are confusing
            return []
        return rows

class paheal(site):
    api_url = "http://rule34.paheal.net/post/list/%s/%i"
    url = "http://rule34.paheal.net/post/list/%s/1"
    regex = '<div class="thumb"\s*data-tags="([\w\s]*)".*_thumbs/([0-9a-f]+)/.*Only</a></div>'
    retries = 2
    def fetch(self, url):
        #paheal has implemented a throttle of one page per two seconds maximum.
        #might as well obey it - going faster isn't going to do much good.
        #it's okay if this crawl takes forever, and playing nice with the sites is a good thing.
        time.sleep(2)

        response = requests.get(url, headers={"User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.52 Safari/536.5"})
        #this is how paheal says it's done
        if response.status_code == 404:
            return None
        return response.text

    def crawl(self, term):
        rows = []
        page = 1
        tag_set = set()

        def get():
            for i in range(self.retries):
                try:
                    return self.fetch(self.get_api_url(term, page))
                except urllib2.HTTPError as e:
                    #that's how paheal does it
                    if e.msg == 'No Images Found':
                        return None
                    else:
                        print e
            print "gave up"
            return None

        while True:
            data = get()
            if not data:
                return rows

            page += 1

            for line in data.splitlines():
                match = re.search(self.regex, line)
                if not match:
                    continue

                tags, md5 = match.groups()
                rows.append(dict(tags=tags.strip(), md5=md5))
                tag_set.update(tags.lower().split())
        if self.alias_check and term not in tag_set:
            #we probably just hit a tag alias
            #and those are confusing
            return []
        return rows

class ponibooru(paheal):
    api_url = 'http://www.ponibooru.org/post/list/%s/%i'
    url = 'http://www.ponibooru.org/post/list/%s/1'
    login_url = 'http://www.ponibooru.org/user_admin/login'
    regex = """<span class="thumb".*img title='([\w\s]*) //.*_thumbs/([0-9a-f]+)/.*</a></span>"""
    retries = 10
    opener = None
    def fetch(self, url):
        if not self.opener:
            #this site won't give you a phpsessid
            #if it doesn't like your user-agent
            #that is so broken it hurts
            sess = requests.session(headers={"User-Agent":"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.52 Safari/536.5"})
            #user/pass to use
            login = json.load(open('ponibooru.auth.json'))

            req = sess.post(self.login_url, data=login)

            
            if login['user'] not in req.text:
                print req.text
                print req.cookies
                raise ValueError("ponibooru didn't listen to our login")
            print "-> URL Opener Created"
            self.opener = sess.get

        response = self.opener(url).text
        #and this is how ponibooru says we're done
        if 'No_Images_Found' in response:
            return None
        return response


genderless_tags = {}
debug_info = {}

def analyze_ratios(posts):

    #It was not until this day
    #that I'd ever expect to find myself writing an algorithm for categorizing sexuality ratios by tag presence.
    #worse, tagging standards are so inconsistent, both across and within sites, that this is basically
    #a messy heurestic.
    #I expect that if anybody starts bikeshedding about my data, it's going to be about this.
    
    #let it be known that the wisdom of the crowd sucks.

    ratios = dict([(category, 0) for category in 
        (
        #it's impossible to distinguish 'bisexual' and 'group' from each other, so we merge them
        'group',
        #herms, intersex, etc all go in here because it's impossible to be more fine-grained than that
        'ambiguous',
        #we subdivide these groups by whether or not they were directly tagged
        'gay', 'male', 'straight', 'female', 'lesbian',
        #or a category was inferred (at which point we can't tell solo from pair if the genders are the same)
        'weakmale', 'weakstraight', 'weakfemale',
        #and unfortunately that's still nowhere near everything
        'unknown'
    )])

    #some sites use name, some sites use pairing flags! everybody's different!

    group_tags = set(('group', 'group_sex', 'bisexual', 'threesome', 'foursome'))
    straight_tags = set(('straight', 'm/f'))
    gay_tags = set(('gay', 'm/m', '2boys'))
    lesbian_tags = set(('lesbian', 'f/f', '2girls'))

    #some sites even use unicode!
    ambiguous_tags = set(('ambiguous', 'ambiguous_gender', 'herm', 'intersex', 'dickgirl', 'futanari', 'futa'))
    male_tags = set(('male', u'\u2642', '1boy'))
    female_tags = set(('female', u'\u2640', '1girl'))

    weak_male_tags = set(('penis', 'yaoi', 'fellatio', 'handjob'))
    weak_female_tags = set(('vagina', 'yuri', 'pussy', 'breasts', 'nipples', 'cunnilingus', 'clitoris'))

    for post_tags, post_sites in posts.values():
        #unfortunately, this is so complicated we have to loop over _EVERY TAG_ to make an informed guess.

        straight_match = gay_match = lesbian_match = male_match = female_match = ambiguous_match = False
        group_match = ambiguous_match = weak_male_match = weak_female_match = False

        for tag in post_tags:
            if tag in group_tags:
                group_match = True
                #group is a bit special - when we find it, we _actually_ know we're done.
                #the category can't change anymore
                break
            elif tag in straight_tags: straight_match = True
            elif tag in gay_tags: gay_match = True
            elif tag in lesbian_tags: lesbian_match = True

            elif tag in ambiguous_tags: ambiguous_match = True
            elif tag in male_tags: male_match = True
            elif tag in female_tags: female_match = True

            elif tag in weak_male_tags: weak_male_match = True
            elif tag in weak_female_tags: weak_female_match = True

            else:
                #still nothing? now we perform the more expensive checks
                
                #r34 uses tags like '3girls' sometimes
                if 'boys' in tag: gay_match = True
                elif 'girls' in tag: lesbian_match = True
                #sometimes people use weird tags like 'long_penis' and nothing else!
                elif 'penis' in tag: weak_male_match = True
                #sometimes people tag 'vaginal_penetration' without 'vagina'!
                elif 'vagina' in tag: weak_female_match = True

                #wc uses tags like 'm/m/f' sometimes
                elif tag.count('/') > 1:
                    if '/?' in tag or '?/' in tag:
                        ambiguous_match = True
                    else:
                        group_match = True
                        break
        
        #only now can we figure out what bucket to put this in
        if sum((straight_match, gay_match, lesbian_match)) > 1:
            #uh oh, we're in more than one bucket that should be mutually exclusive.

            if gay_match and lesbian_match and not straight_match and not male_match and not group_match:
                #people sometimes tag lesbian images with 'gay', which isn't very helpful.
                #if that happened and there's no sign of male bits, let's consider it lesbian.
                ratios['lesbian'] += 1
                #print post_tags
            else:    
            #as far as we can tell, that must mean it's a bi/group piece
                ratios['group'] += 1

        elif group_match:
            ratios['group'] += 1
        elif straight_match:
            ratios['straight'] += 1
        elif gay_match:
            ratios['gay'] += 1
        elif lesbian_match:
            ratios['lesbian'] += 1

        elif ambiguous_match:
            ratios['ambiguous'] += 1
        elif male_match and female_match:
            #sigh. this is a bad place to be in.
            #it's probably a poorly tagged 'straight'. Could also be a herm.
            #let's hope the 'solo' tag exists, at least
            if 'solo' in post_tags:
                ratios['ambiguous'] += 1
            else:
                ratios['weakstraight'] += 1

        elif male_match:
            ratios['male'] += 1
        elif female_match:
            ratios['female'] += 1

        elif weak_male_match and weak_female_match:
            ratios['weakstraight'] += 1
        elif weak_male_match:
            ratios['weakmale'] += 1
        elif weak_female_match:
            ratios['weakfemale'] += 1

        else:
            ratios['unknown'] += 1

    #divisor here is the target width of the ratio chart
    total_size = float(max(1, sum([v for k,v in ratios.items() if k != 'unknown']))) / 100
    all_size = float(max(1, len(posts)))
    ratios.update(
        total_size = total_size,
        all_size = all_size,
    )

    return ratios


def top_25(rows, ratio_key, min_size=0.25):
    def key(row):
        ratios = row['ratios']
        if ratios['unknown'] / ratios['all_size'] < 0.9 and ratios['total_size'] >= min_size:
            if ratio_key == 'allmale':
                return (ratios['weakstraight'] + ratios['straight'] + ratios['male'] + ratios['weakmale'] + ratios['gay']) / ratios['total_size']
            if ratio_key == 'allfemale':
                return (ratios['weakstraight'] + ratios['straight'] + ratios['female'] + ratios['weakfemale'] + ratios['lesbian']) / ratios['total_size']
            if ratio_key == 'straight':
                return (ratios['weakstraight'] + ratios['straight']) / ratios['total_size']
            return ratios[ratio_key] / ratios['total_size']

        return 0

    return sorted(rows, key=key, reverse=True)[:25]
