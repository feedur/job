import re
from dictionaries import merriam_webster, free_dictionary
import multiprocessing
import sqlite3
from functools import partial

dictionary_path = './data/dictionary.db'


def words_of_interest(q, re_exclude='[^A-Za-z]+$|experience|years|certificate|qualification|degree', include_undefined_words = True):
    words = [re.search('[a-z]+', w.lower(), flags=re.IGNORECASE).group() for w in q.split()] # also excludes words that contain no letters
    if re_exclude != '':
        templist = []
        for word in words:
            if not re.match(re_exclude, word, flags=re.IGNORECASE):
                templist.append(word)
        
        words = templist
    
    definitions = define_words(*words)
    search_terms = []
    multi_word_search_terms = []
    undefined_words = []
    for i in range(len(words)):
        pos = definitions[i]
        # looks for nouns as part of search terms
        if pos == 'noun' and not re.search('experience', words[i]):
            search_terms.append(words[i])
        # looks for 2 word terms as potential search term i.e. customer service, mortgage broker
        if pos in ('noun', 'adjective', 'verb') and i < len(words) - 1:
            if definitions[i + 1] == 'noun':
                term = words[i] + ' ' + words[i + 1]
                if not re.search('[^a-z] | [^a-z]', term, re.IGNORECASE): 
                    multi_word_search_terms.append(term)
        
        if pos == 'No Definitions Found':
            undefined_words.append(words[i])

    # looks at 2 word terms and runs them through a dictionary to ensure they are legitimate,
    # then appends them to the list of search terms
    multi_word_def = define_words(*multi_word_search_terms)
    for w,d in list(zip(multi_word_search_terms, multi_word_def)):
        if d == 'No Definitions Found':
            multi_word_search_terms.remove(w)
    
    # exclude single word search terms if they are fully represented by a multiword term
    templist = []
    for w in search_terms:
        include = True
        for x in multi_word_search_terms:
            if w in x:
                include = False
                break
        
        if include:
            templist.append(w)

    search_terms = templist + multi_word_search_terms
    if include_undefined_words:
        search_terms += undefined_words
   
    indexed_search_terms = sorted([(words.index(w.split()[0] if ' ' in w else w), w) for w in search_terms], key=lambda x: x[0]) #this correctly orders the list of words
    search_terms = [w for _,w in indexed_search_terms]

    if len(search_terms) > 0:
        return search_terms
    elif len(undefined_words) > 0:
        return undefined_words
    elif len(words) <= 2:
        return words # if no words are defined and sentence passed has only 1 or 2 words, they are probably product names
    else:
        return []

def define_words(*words, retry=True):
    con = sqlite3.connect(dictionary_path)
    con.execute('CREATE TABLE IF NOT EXISTS dictionary (word TEXT, pos TEXT)')
    output = []
    for w in words:
        con.execute('CREATE TABLE IF NOT EXISTS dictionary (word TEXT, pos TEXT)')
        a = con.execute('SELECT * FROM dictionary WHERE word == ?', (w,)).fetchone()
        output.append([w, a[1] if a != None else None])
    
    not_found_locally = [e[0] for e in output if e[1] == None]
    definitions = multiprocessing.Pool().map(partial(define, retry=retry), not_found_locally)
    redefined_outputs = {w:d for w, d in zip(not_found_locally, definitions)}
    for i in range(len(output)):
        word = output[i][0]
        definition = output[i][1]
        if definition == None:
            output[i][1] = redefined_outputs[word]
            con.execute('INSERT INTO dictionary VALUES (?, ?)', (word, redefined_outputs[word]))

    con.commit()
    con.close()
    final_output = [e[1] for e in output]
    return final_output       


def define(w, retry=False):
    a = free_dictionary(w)
    if a == 'No Definitions Found':
        try:
            a = merriam_webster(w)
        except Exception as e:
            print('merriam webster error:', e)
    
    if a == 'No Definitions Found' and retry:
        w = re.split('[^A-Za-z ]+', w)[0]
        a = define(w)
        
    return a