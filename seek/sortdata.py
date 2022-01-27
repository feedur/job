import sqlite3
import re
from multiprocessing import Process, Queue
import questions
import json

jobs_path = './data/jobs.db'
profile_path = '../profiles/'

def find_jobs(profile_name='tony'):
    with open(profile_path + profile_name + '/info.json', 'r') as f:
        profile = json.loads(f.read())

    if profile['queries'] == []:
        raise 'nothing happened'

    queues, processes = start_processes(profile['queries'], profile['scopes'])
    negative_queues, negative_processes = start_processes(profile['negative_queries'], profile['negative_scopes'])
    positives = [q.get() for q in queues]
    negatives = [q.get() for q in negative_queues]
    [p.join() for p in (processes + negative_processes)]
    return job_gen(positives, negatives)
    
    
def start_processes(queries, scopes):
    default_scope = ['industry', 'sector', 'title']
    queues = []
    processes = []
    for i, words in enumerate(queries):
        if i >= len(scopes):
            scope = default_scope
        elif scopes[i] == []:
            scope = default_scope
        else:
            scope = scopes[i]
        
        q = Queue()
        p = Process(target=search, args=(words, q, scope))
        p.start()
        queues.append(q)
        processes.append(p)

    return queues, processes


def job_gen(positives, negatives):
    jobs_in_negatives = []
    for l in negatives:
        jobs_in_negatives += l

    for job_list in positives:
        other_lists = []
        for li in positives:
            if li != job_list:
                other_lists.append(li)
        
        for job in job_list:
            to_yield = True
            for li in other_lists:
                if job not in li:
                    to_yield = False

            if job in jobs_in_negatives:
                to_yield = False

            if to_yield:
                yield job

#def find_jobs():
#    w1 = ['financial',  'finance', 'equit', 'investment']
#    w2 = ['analy', 'trader', 'banking', 'corporate', 'associate']
#    negs = ['call centre', 'retail', 'customer service','senior', 'relationship', 'manager']
#    negs_scope = ['title', 'details', 'sector', 'industry']
#    ql = [Queue()] * 3
#    pl = [
#        Process(target=search, args=(w1, ql[0])), 
#        Process(target=search, args=(w2, ql[1])), 
#        Process(target=search, args=(negs, ql[2], negs_scope))
#    ]
#    [p.start() for p in pl]
#    s1, s2, n1 = [q.get() for q in ql]
#    [p.join() for p in pl]
#    r = (id for id in s1 if id in s2 and id not in n1)
#    return r # returns a generator of job ids matching the search criteria


def search(words, queue=None, scope=['industry', 'sector', 'title'], negatives=[]): 
    # Returns a generator of Job IDs with the search terms
    for l in [words, negatives, scope]:
        assert type(l) == list, 'inputs in Search() must be lists'
    
    q = construct_search_query(words, scope)
    query = perform_query(q)
    output = None
    if negatives != []:
        q = construct_search_query(negatives, scope)
        nquery = perform_query(q)
        output = [id for id in query if id not in nquery]
    else:
        output = query
    
    if queue == None:
        return output
    else:
        assert 'multiprocessing.queues.Queue object' in queue.__repr__(), 'queue must be a multiprocessing.queue object'
        queue.put(output)

def search_by_location(locations, queue=None):
    query = location_query(locations)
    ids = perform_query(query)
    if queue == None:
        return ids
    else:
        assert 'multiprocessing.queues.Queue object' in queue.__repr__(), 'queue must be a multiprocessing.queue object'
        queue.put(ids)

def location_query(locations):
    # input must be in the format
    # {
    #    'nation': [list of nations],
    #    'state': [list of states],
    #    'city': [list of cities]
    #    ...
    # }
    # list contents are connected by 'or' 
    # keywords (nation, city, etc...) are separated by 'and'

    location_column_names = ['nation', 'state', 'city', 'area', 'suburb'] # names of columns related to location in jobs.db
    for kw in locations:
        if kw not in location_column_names:
            raise ValueError('input must be some dictionary with keywords equal to nation, city, area and suburb and lists as values')
    
    query = []
    for kw in locations:
        query += [construct_search_query(locations[kw], [kw],)]

    joined_query = '(' + ') and ('.join(query) + ')'
    return joined_query


def construct_search_query(words, scope, connector='or'):
    assert type(words) == type(scope) == list, 'params must be lists or iterables'
    query = []
    for s in scope:
        subquery = []
        for w in words:
            subquery.append(s + ' like ' + '"%' + w + '%"')
        
        query.append(f' {connector} '.join(subquery))
    
    query = f' {connector} '.join(query)
    return query
    

def perform_query(q):
    with sqlite3.connect(jobs_path) as con:
        ids = list(id[0] for id in con.execute('SELECT id, title FROM jobs WHERE ' + q))

    con.close()
    return ids


def get_job_details(*ids): 
    con = sqlite3.connect(jobs_path)
    query = 'select details from jobs where '
    id_query = [f'id = {id}' for id in ids]
    split_queries = [query + ' or '.join(id_query[i : i + 200]) for i in range(0, len(id_query), 200)]
    for query in split_queries:
        for details in con.execute(query):
            keywords = analyze_details(details[0])
    
    con.close()
    # output is a dictionary of keywords
    return {k:v for k,v in sorted(keywords.items(), key=lambda d:d[1], reverse=True)}
            

def analyze_details(text, keywords={}): # takes the full job details for a single job as input
    collect = False
    for line in text.split('\n'):
        kw = []
        if re.search('\\b(skills?|responsibilit(y|ies)|qualifications?|degrees?|experience):?\\b', line, re.IGNORECASE): # start collecting keywords when the skills/responsibilities section has been reached
            collect = True

        if re.search('to apply|cover letter|[a-z0-9]+@[a-z0-9]+', line, re.IGNORECASE): # stop collecting keywords when the last few lines have been reached
            collect = False

        if collect:
            kw = questions.words_of_interest(line)
            for w in kw:
                if w not in keywords:
                    keywords[w] = 1
                else:
                    keywords[w] += 1

    return keywords

def delete_old_entries():
    con = sqlite3.connect(jobs_path)
    length = con.execute('SELECT COUNT(*) from jobs').fetchone()[0]
    ids = con.execute("SELECT id FROM jobs ORDER BY id DESC")
    i = 0
    for id in ids:
        i += 1
        if i > length / 4:
            break

        print(id)
 
    con.close()

        

if __name__ == '__main__':
    main()
    
