import urllib2
import time
import random
import re
import base64
import sys
import os
import cPickle as pickle
import csv
import json
import xml.dom.minidom
from operator import itemgetter

#load a bunch of data files
#csv's helpfully provided by the veekun/pokedex project.
pokemon = [
	(int(number), name) for number, sep, name in
		[a.partition(',') for a in 
			open('pokemon.txt').read().splitlines()
		]
	if number
]
pdict = dict(pokemon)

types = dict([(typeid,name) for typeid,name,_,_ in list(csv.reader(open('csv/types.csv')))[1:]])
typedict = dict([((int(num),int(slot)),types[ptype]) for num,ptype,slot in list(csv.reader(open('csv/pokemon_types.csv')))[1:]])

pokemon_species = dict([
	(int(id), (evolves_from_species_id and int(evolves_from_species_id) or None, int(is_baby)))
	for id,identifier,generation_id,evolves_from_species_id,evolution_chain_id,color_id,shape_id,habitat_id,gender_rate,capture_rate,base_happiness,is_baby,hatch_counter,has_gender_differences,growth_rate_id,forms_switchable
 	in list(csv.reader(open('csv/pokemon_species.csv')))[1:]
])
def evolution_level(pokemon_id):
	#it's a little annoying, but determining evolutionary stage
	#requires recursive-walking the chain
	evolves_from, is_baby = pokemon_species[pokemon_id]
	if not evolves_from:
		if is_baby:
			return 'baby'
		return 'basic'
	next = evolution_level(evolves_from)
	if next == 'baby':
		return 'basic'
	if next == 'stage1':
		return 'stage2'
	return 'stage1'

def generation_name(pokemon_id):
	if number >= 493:
		return 'V'
	if number >= 386:
		return 'IV'
	if number >= 251:
		return 'III'
	if number >= 151:
		return 'II'
	return 'I'
	
pokemon_stats = dict()
for pokemon_id,stat_id,base_stat,effort in list(csv.reader(open('csv/pokemon_stats.csv')))[1:]:
	pokemon_id = int(pokemon_id)
	pokemon_stats.setdefault(pokemon_id, 0)
	pokemon_stats[pokemon_id] += int(base_stat)

stat_list = sorted(pokemon_stats.values())
#--
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
	def __init__(self):
		self.pokemon_counts = {}
		self.total_count = 0

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
			rows.extend(data)
			if len(data) < 100:
				#incomplete page means the last page
				break
		return rows




class e621(site):
	api_url = 'http://e621.net/post/index.json?tags=%s+-rating:safe&limit=100&page=%i'
	url = 'http://e621.net/post?tags=%s+rating:explicit&commit=Search'

class wildcritters(site):
	api_url = 'http://wildcritters.ws/post/index.json?tags=%s+-rating:safe&limit=100&page=%i'
	url = 'http://wildcritters.ws/post?tags=%s+rating:explicit'

class rule34(site):
	api_url = 'http://rule34.xxx/index.php?page=dapi&s=post&q=index&tags=%s&pid=%i'
	url = 'http://rule34.xxx/index.php?page=post&s=list&tags=%s'

	def crawl(self, term):
		rows = []
		page = -1 #start page is 0, not 1!
		while True:
			page += 1
			data = urllib2.urlopen(self.get_api_url(term, page)).read()
			data = xml.dom.minidom.parseString(data)
			data = data.getElementsByTagName('post')
			for post in data:
				rows.append(
					{ name:attr.value for (name,attr) in post._attrs.items() }
				)
			if len(data) < 100:
				#incomplete page means the last page
				break
		return rows

sites = dict(
	e621=e621(),
	wildcritters=wildcritters(),
	rule34=rule34(),
)
site_list = sites.values()
#--



def median(values):
	v = sorted(values)
	half = len(v)/2
	if len(v) % 2:
		return v[half]
	return (v[half]+v[half+1])/2

genderless_tags = {}

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

	for post_tags in posts.values():
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

		#gay+straight, etc is considered 'bi/group' here.
		if sum((straight_match, gay_match, lesbian_match)) > 1:
			group_match = True

		if group_match:
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

def debug_tags(number):
	data = all_data[number]

	frequencies = {}
	for post_tags in data.values():
		for tag in post_tags:
			frequencies[tag] = frequencies.setdefault(tag, 0) + 1

	ordered = sorted([(v,k) for k,v in frequencies.items()])
	return ordered
	
if __name__ == '__main__':
	if 'fetch' in sys.argv:
		key = sys.argv[-1]
		site = sites[key]
		pages = dict([(key, {}) for key in sites.keys()])
		try:
			for number, name in pokemon:
				print number, name,
				pages[key][number] = site.crawl(name)
				print
		finally:
			pickle.dump(pages[key], open(site.__class__.__name__ + '.crawl.pickle', 'w'))

	elif 'merge' in sys.argv:
		merged = {}
		site_counts = dict([(site_name, {}) for site_name in sites.keys()])
		

		for site in site_list:
			site.data = pickle.load(open(site.__class__.__name__ + '.crawl.pickle'))
		for number, name in pokemon:
			print number, name,
			by_md5 = {}
			for site_name, site in sites.items():
				site_counts[site_name][number] = len(site.data[number])
				print site_counts[site_name][number],
				for post in site.data[number]:
					md5 = post['md5']
					tags = set(post['tags'].lower().split())

					if md5 in by_md5:
						by_md5[md5].update(tags)
					else:
						by_md5[md5] = tags

			merged[number] = by_md5
			print len(merged[number])

		pickle.dump((merged, site_counts), open('merged.pickle','w'))
		class SetEncoder(json.JSONEncoder):
			def default(self, obj):
				if isinstance(obj, set):
					return list(obj)
				return json.JSONEncoder.default(self, obj)

		json.dump(dict(files=merged, site_counts=site_counts), open('combined_data.json', 'w'), cls=SetEncoder)


	else:
		#Unpickle the html data
		#and prepare counts by pokemon so we can get a total count
		print 'Loading data'
		(all_data, site_counts) = pickle.load(open('merged.pickle'))

		for site_name, site in sites.items():
			for number, name in pokemon:
				site.pokemon_counts[number] = site_counts[site_name][number]

		graph_data = []
		interest_map = {}

		#For each pokemon, generate an "Interest Score" using the following method:
		#Take the number of hits across all sites,
		#then scale relative to the median value (which will become '100%')
		#This expresses the pokemon's value as a percentage-of-the-median.
		for number, name in pokemon:
			interest_score = float(len(all_data[number]))
			interest_map[number] = interest_score
			graph_data.append([number, interest_score])


		#Now that we have that, start building up rows for analysis!
		print 'Creating rows'
		rows = []

		for number, name in pokemon:
			interest_score = interest_map[number]
			
			#get the keys for various attributes
			stage = evolution_level(number)
			stat_percentile = int(float(stat_list.index(pokemon_stats[number])) / len(stat_list) * 10)
			stat_percentile = '%i0%%-%i0%%' % (9-stat_percentile, 10-stat_percentile)
			generation = generation_name(number)
			type1 = typedict.get((number,1),'')
			type2 = typedict.get((number, 2), '')

			row = dict(
				interest_score=interest_score,
				number=number,
				name=name,
				type1=type1,
				type2=type2,
				stage=stage,
				stat_percentile=stat_percentile,
				generation=generation,
				ratios=analyze_ratios(all_data[number]),
			)
			for site_name, site in sites.items():
				row[site_name] = site.pokemon_counts[number]

			rows.append(row)

		rows = sorted(rows, key=itemgetter('interest_score'), reverse=True)

		print "Creating breakdowns"
		#build the grouped breakdown info
		breakdowns = {}
		scale_maxes = {}
		for breakdown_key in ('generation', 'stat_percentile', 'stage', 'type'):
			data_map = {}
			scale_max = 0
			for row in rows:
				if breakdown_key == 'type':
					#types are merged from two fields
					data_map.setdefault(row['type1'], []).append(row['interest_score'])
					if row['type2']:
						data_map.setdefault(row['type2'], []).append(row['interest_score'])
					
				else:
					map_key = row[breakdown_key]
					data_map.setdefault(map_key, []).append(row['interest_score'])

				scale_max = max(scale_max, row['interest_score'])
			breakdowns[breakdown_key] = sorted([
				(median(scores), scores, map_key) for map_key, scores in data_map.items()
			], reverse=True)

			scale_maxes[breakdown_key] = scale_max

		print 'Creating html'
		from jinja2 import Template
		with open('tables.html', 'w') as out:
			out.write(Template(open('html.template').read()).render(
				rows=rows,
				breakdowns=breakdowns,
				scale_maxes=scale_maxes,
				graph_data = json.dumps(graph_data),
				pokemon=json.dumps(dict([(number, name.capitalize()) for number, name in pokemon])),

				sites=sites,
				min=min,max=max,
			))
		print 'Done'

		pokemon_names = set(pdict.values())
		for v,k in sorted([(v,k) for k,v in genderless_tags.items() if k not in pokemon_names]):
			print k,v
