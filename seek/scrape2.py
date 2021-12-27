import requests
from bs4 import BeautifulSoup
import re
import ast
from time import sleep
from random import random
import sqlite3
import threading

jobs_path = './data/jobs.db'

def main():
    global terminate
    terminate = False
    create_sql_db()
    starting_job_id = find_largest_job_id()
    if starting_job_id == None or starting_job_id == '':
        input('enter the id (number at the end of seek.com.au/job/[* this number *]) of a preferably older listing to start search on')
    else:
        starting_job_id += 1

    consec_errors = 0
    for i in range(999999):
        try:
            Page(starting_job_id + i)
            consec_errors = 0
        except Exception as e:
            print(e)
            consec_errors += 1
        
        if consec_errors > 50 or terminate:
            break
            
        sleep(random()/10)

def termination():
    input('any button to terminate')
    global terminate
    terminate = True


def Page(job_id):
    header = {
    "Host": "www.seek.com.au",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:93.0) Gecko/20100101 Firefox/93.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "TE": "trailers"
    }
    base_url = 'https://www.seek.com.au/job/'
    url = base_url + str(job_id)
    r = requests.get(url, headers=header)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'lxml')
    tag, = soup.select('[data-automation="job-detail-page"]')
    
    # first parse goes through main body of each listing to obtain most of the information, not all especially
    # job location and job industry / sector are hard to parse effectively as id's are not in the tag
    values = {
        'job-detail-title': [], 
        'advertiser-name': [], 
        'jobAdDetails': [], 
        'job-detail-page': [], 
        'job-detail-work-type': []
    }
    for s in tag.strings:
        if re.search('[A-Za-z]', s):
            v = '' + s
            for i in range(50):
                s = s.parent
                val = s.attrs.get('data-automation')
                if val in values and val != None:
                    values[val].append(v.strip())
                    break
    
    # This part attempts to parse the script tag from the end from the end of the html file with the attribute of 
    # data-automation = server-state as it contains easily organised job location, job sector / industry
    tags = soup.body.find_all('script')
    for tag in tags:
        if 'server-state' == tag.attrs.get('data-automation'):
            tt = tag.text
            break
    
    length = len('window.SEEK_REDUX_DATA = ')
    a = tt.index('window.SEEK_REDUX_DATA = ')
    b = tt.index('window.SEEK_APP_CONFIG = ')
    tt = tt[a + length : b].strip()
    a = tt.index('"locationHierarchy":')
    b = tt.index(',"salary"')
    tt = tt[a:b]
    replacements = {
        'true': 'True',
        'false': 'False',
        'nothing': 'None',
        'undefined': 'None',
        'none': 'None',
        'null': 'None'
    }
    for rep in replacements:
        tt = tt.replace(rep, replacements[rep])

    d = ast.literal_eval('{'+ tt +'}')
    # end of second part, d is the dictionary representing the results of this section
    output = {
        'id': job_id,
        'title': values['job-detail-title'][0],
        'company': values['advertiser-name'][0],
        'nation': d['locationHierarchy']['nation'],
        'state': d['locationHierarchy']['state'],
        'city': d['locationHierarchy']['city'],
        'area': d['locationHierarchy']['area'],
        'suburb': d['locationHierarchy']['suburb'],
        'sector_id': d['classification']['id'],
        'sector': d['classification']['description'],
        'industry_id': d['subClassification']['id'],
        'industry': d['subClassification']['description'],
        'work_type': '\n'.join(values['job-detail-work-type']),
        'details': '\n'.join(values['jobAdDetails'])
    }
    
    with sqlite3.connect(jobs_path) as con:
        con.execute(
            'INSERT INTO jobs VALUES (' + ','.join(['?' for i in range(14)]) + ')',
            [output[o] for o in output]
        )

    con.close()
    print(output['title'], end = '\t')
    print(output['company'])


def find_largest_job_id():
    with sqlite3.connect(jobs_path) as con:
        largest = con.execute('SELECT MAX(id) FROM jobs').fetchall()[0][0]

    con.close()
    return largest


def create_sql_db():
    with sqlite3.connect(jobs_path) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS jobs
            (id INT, title TEXT, company TEXT, nation TEXT, state TEXT, city TEXT, area TEXT, suburb TEXT, 
            sector_id INT, sector TEXT, industry_id INT, industry TEXT, work_type TEXT, details TEXT)''')
        con.execute('''CREATE TABLE IF NOT EXISTS applications (id INT, status TEXT)''')

    con.close()


if __name__ == '__main__':
    t = threading.Thread(target=termination)
    t.start()
    main()