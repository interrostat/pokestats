import urllib2
import time
import random
import re
import base64
import sys
import os
import pickle
import csv


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
	evolves_from, is_baby = pokemon_species[pokemon_id]
	#print pokemon_id, evolves_from, is_baby
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
	
pokemon_stats = dict()
for pokemon_id,stat_id,base_stat,effort in list(csv.reader(open('csv/pokemon_stats.csv')))[1:]:
	pokemon_id = int(pokemon_id)
	pokemon_stats.setdefault(pokemon_id, 0)
	pokemon_stats[pokemon_id] += int(base_stat)

stat_list = sorted(pokemon_stats.values())
#--

e6URL = base64.b64decode('aHR0cDovL2U2MjEubmV0L3Bvc3Q=')
wcURL = base64.b64decode('aHR0cDovL3dpbGRjcml0dGVycy53cy9wb3N0')
r34URL = base64.b64decode('aHR0cDovL3J1bGUzNC54eHgvaW5kZXgucGhw')

def e6(query):
	return e6URL + '?tags=%s&commit=Search' % urllib2.quote(query)

def wc(query):
	return wcURL + '?tags=%s' % urllib2.quote(query)

def r34(query):
	return r34URL + '?page=post&s=list&tags=%s' % urllib2.quote(query)

#--

def count_results(query, data):
	ret = re.findall('%s.*?"post-count">(\d+)</span>' % query, data)
	if not ret:
		return 0
	return int(ret[0])

def r34_count_results(query, data):
	ret = re.findall('>%s<.*?>(\d+)<' % query, data)
	if not ret:
		return 0
	return int(ret[0])

def get(query):
	data = urllib2.urlopen(r34(query)).read()
	return data

def median(values):
	v = sorted(values)
	half = len(v)/2
	if len(v) % 2:
		return v[half]
	return (v[half]+v[half+1])/2
	
if __name__ == '__main__':
	if 'fetch' in sys.argv:
		pages = {}
		try:
			for number, name in pokemon:
				print number, name
				pages[number] = get(name)
		finally:
			pickle.dump(pages, open('data.pickle', 'w'))
	else:
		wc_data =  pickle.load(open('wc.pickle'))
		e6_data =  pickle.load(open('e6.pickle'))
		r34_data =  pickle.load(open('r34.pickle'))
		counts = []
		typecounts = {}
		gencounts = {}
		stagecounts = {}
		percentilecounts = {}
		allcounts = []

		e6_counts = {}
		wc_counts = {}
		r34_counts = {}
		for number, name in pokemon:
			e6_counts[number] = count_results(name, e6_data[number])
			wc_counts[number] = count_results(name, wc_data[number])
			r34_counts[number] = r34_count_results(name, r34_data[number])

		total_e6_count = float(sum([x for x in e6_counts.values()]))
		total_wc_count = float(sum([x for x in wc_counts.values()]))
		total_r34_count = float(sum([x for x in r34_counts.values()]))

		count_map = {}

		for number, name in pokemon:
			e6_count, wc_count, r34_count = e6_counts[number], wc_counts[number], r34_counts[number]
			best_count = sum((e6_count/total_e6_count, wc_count/total_wc_count, r34_count/total_r34_count))/3
			count_map[number] = best_count
			allcounts.append(best_count)
		


		mediancount = median(allcounts)

		for number, best_count in count_map.items():
			count_map[number] = best_count / mediancount * 100

		for number, name in pokemon:
			best_count = count_map[number]
			e6_count, wc_count, r34_count = e6_counts[number], wc_counts[number], r34_counts[number]
			#male_count = max(count_results('=male', e6_data[number]), count_results('%E2%99%82', wc_data[number]))
			#female_count = max(count_results('=female', e6_data[number]), count_results('%E2%99%80', wc_data[number]))
			stage = evolution_level(number)
			percentile = int(float(stat_list.index(pokemon_stats[number])) / len(stat_list) * 10)

			#print number, name, evolution_level(number)

			gender_ratio = '' #'%.1f%%' % ((float(male_count) / max(male_count + female_count, 1)) * 100)

			type1 = typedict.get((number,1),'')
			type2 = typedict.get((number, 2), '')
			if type1:
				typecounts.setdefault(type1, []).append(best_count)
			if type2:
				typecounts.setdefault(type2, []).append(best_count)
			generation = 'I'
			if number >= 151:
				generation = 'II'
				if number >= 251:
					generation = 'III'
					if number >= 386:
						generation = 'IV'
						if number >= 493:
							generation = 'V'

			gencounts.setdefault(generation, []).append(best_count)
			stagecounts.setdefault(stage, []).append(best_count)
			percentilecounts.setdefault(percentile, []).append(best_count)

			counts.append([
				best_count, e6_count, wc_count, r34_count, number, gender_ratio, name, type1, type2, stage
			])
		#print counts[:10]
		counts = sorted(counts, reverse=True)


		typecounts = sorted([(median(items),items,name) for name,items in typecounts.items()], reverse=True)
		gencounts = sorted([(median(items),items,name) for name,items in gencounts.items()], reverse=True)
		stagecounts = sorted([(median(items),items,name) for name,items in stagecounts.items()], reverse=True)
		percentilecounts = sorted([(median(items),items,name) for name,items in percentilecounts.items()], reverse=True)
		#print typecounts

		
		#type_writer = csv.writer(open('typecounts.csv', 'w'))
		#type_writer.writerows(typecounts)
		#writer = csv.writer(open('counts.csv', 'w'))
		#writer.writerows(counts)
		print 'Creating HTML'
		from jinja2 import Template
		with open('tables.html', 'w') as out:
			out.write(Template(open('html.template').read()).render(
				counts=counts,
				typecounts=typecounts,
				gencounts=gencounts,
				stagecounts=stagecounts,
				percentilecounts=percentilecounts,
				allcounts=allcounts,
				typemax = max([max(i) for _,i,_ in typecounts]),
				genmax = max([max(i) for _,i,_ in gencounts]),
				stagemax = max([max(i) for _,i,_ in stagecounts]),
				percentilemax = max([max(i) for _,i,_ in percentilecounts]),
				mediancount = mediancount,

				min=min,max=max,e6=e6,wc=wc,r34=r34
			))
		print 'Done'
