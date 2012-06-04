import urllib
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


#load a bunch of data files
#csv's helpfully provided by the veekun/pokedex project.
print "Parsing initial data"
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
official_names = dict([
	(int(pokemon_species_id),name.decode('utf8').encode('ascii', 'xmlcharrefreplace'))
	for pokemon_species_id,local_language_id,name,genus
	in list(csv.reader(open('csv/pokemon_species_names.csv')))[1:]
	if int(local_language_id) == 9
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
from common import *

sites = dict(
	e621=e621(),
	paheal=paheal(),
	wildcritters=wildcritters(),
	wildcrittersnet=wildcrittersnet(),
	rule34=rule34(),
)
site_list = sites.values()
#--


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

	if 'merge' in sys.argv:
		merged = {}
		site_counts = dict([(site_name, {}) for site_name in sites.keys()])
		

		for site in site_list:
			site.data = pickle.load(open(site.__class__.__name__ + '.crawl.pickle'))
			site.md5s = set()
			site.tag_counts = []

		for number, name in pokemon:
			print number, name,
			by_md5 = {}
			for site_name, site in sites.items():
				site_counts[site_name][number] = len(site.data[number])
				print site_counts[site_name][number],
				for post in site.data[number]:
					md5 = post['md5']
					site.md5s.add(md5)

					tags = set(post['tags'].lower().split())
					site.tag_counts.append(len(tags))

					if md5 in by_md5:
						existing_tags, existing_sites = by_md5[md5]
						existing_tags.update(tags)
						existing_sites.update([site_name])
					else:
						by_md5[md5] = tags, set([site_name])

			merged[number] = by_md5
			print len(merged[number])

		pickle.dump((merged, site_counts), open('merged.pickle','w'))

		json.dump(dict(files=merged, site_counts=site_counts), open('combined_data.json', 'w'), cls=SetEncoder)

		for site_name, site in sites.items():
			unique = site.md5s.difference(*[s.md5s for s in site_list if s != site])
			print site_name, 'has', len(site.md5s), 'posts, with', len(unique), 'uniques and averaging', float(sum(site.tag_counts))/len(site.tag_counts),'tags'


	if 'analyze' in sys.argv:
		#Unpickle the html data
		#and prepare counts by pokemon so we can get a total count
		print 'Loading data'
		(all_data, site_counts) = pickle.load(open('merged.pickle'))
		print 'Loading more data'
		prior_data = json.load(open('may_data/combined_data.json'))
		(prior_all_data, prior_site_counts) = prior_data['files'], prior_data['site_counts']
		#one problem is that the json data strings the keys
		for key in prior_all_data.keys():
			prior_all_data[int(key)] = prior_all_data[key]

		delta_site_counts = dict([(site_name, dict()) for site_name in sites.keys()])

		for site_name, site in sites.items():
			for number, name in pokemon:
				site.pokemon_counts[number] = site_counts[site_name][number]

				delta_site_counts[site_name][number] = set()

		graph_data = []
		swapped_graph_data = []
		interest_map = {}
		delta_interest_map = {}

		print "Creating Deltas"
		minus_sites = set([site_name for site_name in sites.keys() if site_name not in prior_site_counts])

		delta_data = dict()
		delta_all_data = dict()
		for number, name in pokemon:
			delta_data[number] = dict()
			delta_all_data[number] = dict()
			for md5, (tags, site) in all_data[number].items():
				if set(site) - minus_sites:
					#if name == 'glaceon': print 'old sites', md5, site
					delta_all_data[number][md5] = (tags, site)
					if md5 not in prior_all_data[number]:
						if name == 'glaceon': print 'new', md5, site
						delta_data[number][md5] = (tags, site)
						for site_name in site:
							delta_site_counts[site_name][number].add(md5)

		#find the total score and store it in various places
		for number, name in pokemon:
			interest_score = float(len(all_data[number]))
			interest_map[number] = interest_score
			delta_interest_map[number] = float(len(delta_data[number]))
			graph_data.append([number, interest_score])
			swapped_graph_data.append([interest_score, number])


		#make an ordered version of the graph data
		ordered_graph_data = []
		reorderings = {}
		for i, (interest_score, number) in enumerate(sorted(swapped_graph_data, reverse=True)):
			reorderings[i] = number
			ordered_graph_data.append([i, interest_score])

		#Now that we have that, start building up rows for analysis!

		print 'Creating rows'
		rows = []
		delta_rows = []

		for number, name in pokemon:
			interest_score = interest_map[number]
			delta_interest_score = delta_interest_map[number]
			
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
			delta_row = dict(
				interest_score=delta_interest_score,
				number=number,
				name=name,
				type1=type1,
				type2=type2,
				stage=stage,
				stat_percentile=stat_percentile,
				generation=generation,
				ratios=analyze_ratios(delta_data[number]),
			)
			for site_name, site in sites.items():
				row[site_name] = site.pokemon_counts[number]
				delta_row[site_name] = len(delta_site_counts[site_name][number])

			rows.append(row)
			delta_rows.append(delta_row)

		rows = sorted(rows, key=itemgetter('interest_score'), reverse=True)
		delta_rows = sorted(delta_rows, key=itemgetter('interest_score'), reverse=True)

		print "Creating breakdowns"
		#build the grouped breakdown info
		breakdowns = {}
		scale_max = 0
		for breakdown_key in ('generation', 'stat_percentile', 'stage', 'type'):
			data_map = {}
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

		print "Finding Pairings"
		#remap pairings
		file_pokemon = {}
		for number, name in pokemon:
			delta_data[number] = dict()
			for md5, (tags, site) in all_data[number].items():
				file_pokemon.setdefault(md5,[]).append(number)

		pair_counts = collections.Counter()
		triple_counts = collections.Counter()
		for md5, numbers in file_pokemon.items():
			if len(numbers) > 1:
				pair_counts.update(itertools.combinations(sorted(numbers), 2))
				triple_counts.update(itertools.combinations(sorted(numbers), 3))

		adjusted_pairs = collections.Counter()
		adjusted_triples = collections.Counter()
		for (first, second), count in pair_counts.items():
			count = float(count)
			adjusted_pairs[(first, second)] = count * (count / interest_map[first]) * (count / interest_map[second])

		for (first, second, third), count in triple_counts.items():
			count = float(count)
			adjusted_triples[(first, second, third)] = count * (count / interest_map[first]) * (count / interest_map[second]) * (count / interest_map[third])


		top_pairs = []
		for (first, second), count in adjusted_pairs.most_common(25):
			top_pairs.append(dict(
				first=first,
				second=second,
				interest_score=count,
				ratios=analyze_ratios(dict([
					(md5, all_data[first][md5])
					for md5,numbers in file_pokemon.items()
					if first in numbers and second in numbers
				]))
			))

		top_triples = []
		for (first, second, third), count in adjusted_triples.most_common(25):
			top_triples.append(dict(
				first=first,
				second=second,
				third=third,
				interest_score=count*100,
				ratios=analyze_ratios(dict([
					(md5, all_data[first][md5])
					for md5,numbers in file_pokemon.items()
					if first in numbers and second in numbers and third in numbers
				]))
			))

		print 'Writing Data'
		json.dump(dict(
			rows=rows,
			delta_rows=delta_rows,
			
			breakdowns=breakdowns,
			scale_max=scale_max,
			
			graph_data = json.dumps(graph_data),
			ordered_graph_data = json.dumps(ordered_graph_data),
			reorderings = json.dumps(reorderings),

			pokemon=json.dumps(dict([(number, official_names[number]) for number, name in pokemon])),
			
			site_counts = site_counts,
			delta_site_counts = delta_site_counts,
			
			top_pairs = top_pairs,
			top_triples = top_triples,

		), open('analyzed.json', 'w'), cls=SetEncoder)

		pokemon_names = set(pdict.values())
		for v,k in sorted([(v,k) for k,v in genderless_tags.items() if k not in pokemon_names]):
			print k,v

	if 'html' in sys.argv:
		kwargs = json.load(open('analyzed.json'))
		for site_name, site in sites.items():
			for number, name in pokemon:
				site.pokemon_counts[number] = kwargs['site_counts'][site_name][str(number)]

		print 'Creating html'
		from jinja2 import Template, Environment, PackageLoader
		env = Environment(loader=PackageLoader(__name__, 'templates'))
		for template_file in ('index', 'chart', 'faq', 'breakdowns', 'linecharts'):
			print "Generating", template_file
			with open('html/%s.html' % template_file, 'w') as out:
				out.write(env.get_template('%s.template.html' % template_file).render(
					sites=sites,
					official_names=official_names,

					#functions
					min=min,max=max,quote=urllib.quote,top_25=top_25,
					**kwargs
				))
		print 'Done'
