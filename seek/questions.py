from copy import copy
from bs4 import BeautifulSoup
import re
from kw import *

resume_path = '../resume/tech/resume.txt'

def get_questions(page=None, print_output=False):
    if page == None:
        page = BeautifulSoup(open('questions.html', 'r'), 'lxml')
    
    questions = []
    answers = []
    # find interactable tags
    for tag in page.descendants:
        q = {'tag': tag}
        if tag.name == 'select':
            q['type'] = ['select']
            q['answers'] = []
            # select tag should contain option tags with answer strings as their children
            empty_options = 0
            for t in tag.find_all('option'): 
                assert len(list(t.strings)) <= 1, 'more than 1 string per option'
                q['answers'].append({'tag' : t, 'a' : t.string})
                if t.string == None:
                    empty_options += 1
            
            assert empty_options < 2, 'more 1 option has no string'
            p_tag = tag
            for i in range(20):
                p_tag = p_tag.parent
                if p_tag.text != tag.text:
                    assert tag.text in p_tag.text, 'parent tag strings'
                    assert len(list(tag.stripped_strings)) + 1 == len(list(p_tag.stripped_strings)), 'parent tag strings' 
                    q['q'] = p_tag.text.replace(tag.text, '')
                    break
            
            questions.append(q)
        # a little too specific
        if tag.name == 'input' and 'toggle' not in tag.attrs['id'].lower(): # excludes inputs which are not also related to questions
            q['type'] = ['input'] + [tag.attrs['type']]
            # looks for answer string within tag
            # then looks for answer string within siblings of tag
            while tag.text == '':
                tag = tag.next_sibling
                assert tag != None, 'ran out of siblings'
                if len(list(tag.stripped_strings)) > 0:
                    text, = tag.stripped_strings # throws an error if more than 1 string found
            
            q['a'] = text
            assert text != None, 'answer string not found'
            answers.append(q)

    #this section purely handles input tags
    for ans in answers:
        tag = ans['tag']
        related_answers = [] # creates a list of answers to the question
        # gets tag that contains all the answers to a question
        while tag.text in ('', ans['a']):
            tag = tag.parent
        
        # check that tags found are answers of the same question
        for t in tag.children:
            t_matches = 0
            for a in answers:
                if str(a['tag']) in str(t):
                    t_matches += 1
                    related_answers.append(a)

            assert t_matches == 1, 'answer tag should contain only 1 answer'

        p_tag = tag
        while p_tag.text == tag.text:
            p_tag = p_tag.parent
        
        # checks that parent tag containing question contains answer tags as well
        for r in related_answers:
            assert str(r['tag']) in str(p_tag)
        
        # checks that parent tag containing question does not contain answer tags that are also assigned to other parent tags
        for a in answers:
            assert str(a['tag']) not in str(p_tag) or a in related_answers
        
        q_a_text = list(p_tag.stripped_strings)
        for r in related_answers:
            q_a_text.remove(r['a'])
    
        questions.append({
            'tag' : p_tag, # this tag is almost always useless if the question type is input
            'type': ans['type'],
            'q' : q_a_text[0],
            'answers': [a for a in related_answers]
        })
            
    # Removes duplicate questions based on question string generated in previous steps
    final_list = [questions[0]]
    for q in questions:
        include = True
        for qf in final_list:
            if q['q'] == qf['q']:
                include = False
        
        if include:
            final_list.append(q)
    
    if print_output: # prints output only if print_output is true
        for q in final_list:
            print()
            print(q['q'])
            print(q['type'])
            for e in q['answers']:
                print('\t', e['a'])
            print()

    return final_list # list of questions


def answer_question(q, resume=None):
    # with a single question, q of the structure:
    # {
    #   'tag': tag (bs4.tag),
    #   'q': question (string),
    #   'type': [type (e.g. select, input, form), subtype (e.g. radio)]
    #   'answers': [{'tag': tag (bs4.tag), 'a': answer (string)}, ...]
    # }
    # res should be a regex to determine list of valid answers
    
    tags = ms_office_checkbox(q)
    if tags == False:
        res = question_keywords(q) 
        valid_answers = get_answers(q['answers'], res)
        tags = question_type(q, valid_answers)

    return tags

def ms_office_checkbox(q):
    ms_matches = 0
    if 'microsoft office' in q['q'].lower():
        if q['type'][1] == 'checkbox':
            for a in q['answers']:
                for ms_product in ['onenote', 'word', 'excel', 'powerpoint']:
                    if ms_product in a['a'].lower():
                        ms_matches += 1
                        break

    if ms_matches > 1:
        tags = []
        valid_answers = get_answers(q['answers'], '!not regex, search answers')
        checked_answers = get_checked_answers(q)
        for answer in q['answers']:
            if (answer in valid_answers) ^ (answer in checked_answers):
                tags.append(answer['tag'])

        return tags
    else:
        return False

def get_checked_answers(q):
    output = []
    for answer in q['answers']:
        checked = answer['tag'].attrs['aria-checked']
        if checked == 'true':
            output += [answer]
    
    return output

def question_keywords(q):
    r = '!undefined'
    s = lambda regex, text=q['q']: re.search(regex, text, flags=re.IGNORECASE)
    if s('experience|years|certificate|qualification|degree|(?=.*have)(?=.*work ed)|working'):
        keywords = words_of_interest(q['q'])
        if keywords == []: # no words of interest in question found
            r = '!not regex, search answers'
        else:
            r = search_resume(*keywords)

    #australian or nz citizenship
    elif s('(?=.*australia)(?=.*citizen)|(?=.*work)(?=.*right)|citizen|sponsorship|(?=.* nz )|(?=.*new zealand)'):
        r = 'citizen|yes'
    
    #covid vaccination
    elif s('vaccine|covid|vaccination'):
        r = 'fully|double|both|complete|yes'

    #language
    elif s('(?=.*english)(?=.*proficiency)|(?=.*english)(?=.*language)'):
        r = 'native|proficient|yes'

    #salary expectations
    elif s('salary'):
        r = '60k|60000|60,000'

    #notice period
    elif s('how.*much.*notice|notice.*period'):
        r = '2.*weeks|1.*month'

    #highest level of education
    elif s('education.*level|highest.*education|tertiary.*education'):
        r = 'yes|tertiary|master*.degree|masters'

    assert r != '!undefined', 'question does not fit in programming; ' + str(q['q'])   
    return r


def get_answers(answers, regex):
    output = []
    if '!not regex' not in regex:
        for a in answers:
            if valid_answer(a['a'], regex):
                output.append(a)
    
    elif 'search answers' in regex:
        none_answer = None
        for a in answers:
            keywords = words_of_interest(a['a'])
            if valid_answer(a['a'], r'\bnone\b|don\'t|\bno\b'):
                none_answer = a['tag']

            elif search_resume(*keywords, return_type='boolean'):
                output.append(a)
            
        if output == [] and none_answer != None:
            output.append(none_answer)
            
    return output


def question_type(q, valid_answers):
    if q['type'][0] == 'select':
        return [q['tag'], valid_answers[0]['tag']]
    
    elif q['type'][0] == 'input':
        if 'radio' in q['type'][1]:
            return [valid_answers[0]['tag']]
        elif 'checkbox' in q['type'][1]:
            raise Exception('can\'t handle non microsoft related checkboxes yet')
    

# every word passed must match resume to evaluate true
def search_resume(*words, return_type='regex'):
    with open(resume_path, 'r') as f:
        resume = f.read()
    
    result = False
    for w in words:
        if not re.search(w, resume, flags=re.IGNORECASE):
            result = False
            break
        else:
            result = True
    
    if return_type != 'regex':
        return result
    elif result:
        return 'yes|1|2'
    else:
        return 'no|0|1|never|negative'

def valid_answer(a, regex):
    if a == None:
        return False
    
    if re.search(regex, a, flags=re.IGNORECASE):
        return True
    else:
        return False
        

if __name__ == '__main__':
    questions = get_questions(print_output=True)
    output = answer_question(questions[1])
    print(output)
