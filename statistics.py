import urllib2
import time
import random
import re
import base64
import sys
import os
import pickle
import csv
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

	def count_results(self, term, data):
		if term in self.translations:
			term = self.translations[term]
		ret = re.findall('%s.*?"post-count">(\d+)</span>' % term, data)
		if not ret:
			return 0
		return int(ret[0])

	def translate(self, term):
		#Turn a name into a URL term
		#and fixup any site-specific peculiarities
		if term in self.translations:
			return self.translations[term]
		return urllib2.quote(term)

	def get_url(self, term):
		return self.url % self.translate(term)

	def get(self, term):
		data = urllib2.urlopen(self.get_url(term)).read()
		return data

class e621(site):
	url = 'http://e621.net/post?tags=%s+rating:explicit&commit=Search'
	data_file_name = 'e6.pickle'

class wildcritters(site):
	url = 'http://wildcritters.ws/post?tags=%s+rating:explicit'
	data_file_name = 'wc.pickle'

class rule34(site):
	url = 'http://rule34.xxx/index.php?page=post&s=list&tags=%s'
	data_file_name = 'r34.pickle'
	
	def count_results(self, term, data):
		if term in self.translations:
			term = self.translations[term]
		ret = re.findall('>%s<.*?>(\d+)<' % term, data)
		if not ret:
			return 0
		return int(ret[0])

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
	
if __name__ == '__main__':
	if 'fetch' in sys.argv:
		key = sys.argv[-1]
		site = sites[key]
		pages = dict([(key, {}) for key in sites.keys()])
		try:
			for number, name in pokemon:
				print number, name,
				pages[key][number] = site.get(name)
				print
		finally:
			pickle.dump(pages[key], open(site.data_file_name, 'w'))
	else:
		#Unpickle the html data
		#and prepare counts by pokemon so we can get a total count
		print 'Loading data'
		for site in site_list:
			site.data = pickle.load(open(site.data_file_name))
			for number, name in pokemon:
				site.pokemon_counts[number] = site.count_results(name, site.data[number])
			site.total_count = float(sum(site.pokemon_counts.values()))
		interest_list = []
		interest_map = {}

		#For each pokemon, generate an "Interest Score" using the following method:
		#Take the number of hits per site, divided by site size, average those values,
		#then scale relative to the median value (which will become '100%')
		#This expresses the pokemon's value as a percentage-of-the-median.
		for number, name in pokemon:
			interest_scores = [site.pokemon_counts[number] / site.total_count for site in site_list]
			interest_score = sum(interest_scores) / len(interest_scores)
			interest_map[number] = interest_score
			interest_list.append(interest_score)
		
		median_interest = median(interest_list)

		for number, interest_score in interest_map.items():
			interest_map[number] = interest_score / median_interest * 100

		interest_list = [interest_score / median_interest * 100 for interest_score in interest_list]

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
				interest_list = interest_list,

				sites=sites,
				min=min,max=max,
			))
		print 'Done'
