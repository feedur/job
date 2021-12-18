from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as ec
from time import sleep
from random import random
from sortdata2 import find_jobs
from bs4 import BeautifulSoup
import sqlite3
from questions import get_questions, answer_question
from threading import Thread
from time import time
from sortdata2 import get_job_details
import sys
sys.path.append('./data')
from recruiters import recruiters
import os

jobs_path = './data/jobs.db'
geckodriver_path = '/Users/tony/Documents/programming/job-search/env/geckodriver'
SEEK_USERNAME = os.environ.get('SEEK_USERNAME')
SEEK_PASSWORD = os.environ.get('SEEK_PASSWORD')


def main(exclude_recruiters=True, ignore_errors=True):
    ids = (id for id in find_jobs() if id not in already_applied())
    sk = Seek()
    for id in ids:
        status = None
        print('applying:', id)
        if exclude_recruiters:
            status = if_recruiter(id) #returns None if the company to the id is not a recruitment firm
        
        if status == None:
            for i in range(2):
                try:
                    status = apply(id, sk)
                    break
                except Exception as e:
                    status = e
                    if not ignore_errors:
                        raise e
        
        with sqlite3.connect(jobs_path) as con:
            con.execute('INSERT INTO applications VALUES (?, ?)', (str(id), str(status)))
            print(id, status)
        
        con.close()

    print('ran out of jobs to apply for')
    sk.driver.close()

def already_applied():
    with sqlite3.connect(jobs_path) as con:
        ids = [value[0] for value in con.execute('SELECT id FROM applications')]

    con.close()
    return ids

def apply(id=55137148,sk=None):
    if sk == None:
        sk = Seek()

    sk.Get(id)
    # main job page
    try:
        e = sk.Clickable('//a[@data-automation="job-detail-apply"]')
    except:
        return 'does not exist'

    # determines if the apply button links to an external link, returns immediately
    source = BeautifulSoup(e.get_attribute('outerHTML'), 'lxml') 
    href = source.html.body.contents[0].attrs['href']
    if 'linkout' in href:
        return 'external link'
    
    e.click()
    
    # login
    # this page only appears on the first application
    try:    
        sk.Enter_username()
        sk.Enter_password()
    except: 
        pass
    
    # step 1 choose documents (resume/cover letter)
    sk.Select_resume()
    sk.Include_cover_letter()
    con_btn = '//button[@data-testid="continue-button"]'
    sk.Clickable(con_btn).click()
    
    # step 2 answer employer questions
    sk.Clickable(con_btn) # waits for page to load first by waiting for button to be clickable
    page = sk.driver.page_source
    with open('questions.html', 'w') as f:
        f.write(page)

    bsoup = BeautifulSoup(page, 'lxml')
    if bsoup.title.text == 'Step 2 Answer employer questions':
        questions = get_questions(page=bsoup)
        for q in questions:
            tags = answer_question(q)
            for tag in tags:
                xpath = '//' + tag.name
                for attr in tag.attrs:
                    if type(tag.attrs[attr]) == list:
                        attributes = ' '.join(tag.attrs[attr])
                    elif type(tag.attrs[attr]) == str:
                        attributes = tag.attrs[attr]

                    xpath += '[@' + attr + '="' + attributes + '"]'
            
                # waiting for an input/radio tag to be clickable doesn't work
                sk.Presence(xpath).click()

        sk.Clickable(con_btn).click()
                
    # step 3 update seek profile
    sk.Presence(con_btn)
    sk.Clickable(con_btn).click()
    # step 4 review and submit
    sk.Clickable('//button[@data-testid="review-submit-application"]').click()
    return 'applied'


class Seek():
    def __init__(self, username=SEEK_USERNAME, password=SEEK_PASSWORD):
        self.driver = webdriver.Firefox(executable_path=geckodriver_path)
        self.username = username
        self.password = password

    def Get(self, id):
        self.driver.get('https://www.seek.com.au/job/' + str(id))

    def Clickable(self, search):
        sleep(random() + 1)
        return WebDriverWait(self.driver, 10).until(ec.element_to_be_clickable(('xpath', search)))

    def Presence(self, search):
        sleep(random() + 1)
        return WebDriverWait(self.driver,10).until(ec.presence_of_element_located(('xpath', search)))
    
    def Enter_form(self, search, input):
        e = self.Clickable(search)
        return e.send_keys(input)

    def Enter_username(self, search='//input[1]', inp=None):
        inp = self.username + Keys.ENTER if inp == None else inp
        return self.Enter_form(search, inp)
    
    def Enter_password(self, search='//input[@id="password"]', inp=None):
        inp = self.password + Keys.ENTER if inp == None else inp
        return self.Enter_form(search, inp)

    def Select_resume(self, search='//select[@id="selectedResume"]'):
        e = self.Presence(search)
        e.click()
        sleep(random() + 1)
        s = Select(e)
        return s.select_by_index(1)

    def Upload_resume(self, search='//input[@id="resume-upload"]', upload_path='/Users/tony/Documents/programming/other/resume/analyst/resume.pdf'):
        return self.Presence(search).send_keys(upload_path)

    def Delete_resume(self):
        self.Presence('//span[@class="_12ytqjg0 _1ov61rv12 _1ld5v2h1 _1ov61rv2 _1kzqo4e24"]').click()
        return self.Presence('//button[@data-testid="delete-confirmation"]').click()

    def Include_cover_letter(self, option=2):
        # Options:
        # 0: upload cover letter
        # 1: write cover letter
        # 2: don't include cover letter

        self.Presence(f'//input[@id="coverLetter_{option}"]').click()

def terminate(sk, termination):
    input('any button to terminate:')
    termination = True

def if_recruiter(id):
    con = sqlite3.connect(jobs_path)
    company = con.execute('SELECT company FROM jobs WHERE id = ?', [id]).fetchone()[0]
    for r in recruiters:
        if r in company.lower():
            return 'recruiter'
    
    return None

# future use, confirms presence of tab/ external url and switches to tab
def external_link(sk): 
    tabs = sk.driver.window_handles
    sk.driver.switch_to.window(tabs[-1])
    WebDriverWait(sk.driver, 10).until(checkurl)
    if 'seek.com' not in sk.driver.current_url:
        return 'external link'

def checkurl(driver):
    url = driver.current_url
    while url == driver.current_url:
        sleep(0.1)
    
    return True


if __name__ == "__main__":
    main()
