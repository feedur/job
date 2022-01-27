import re
import spacy
import pandas as pd
import sqlite3


jobs_path = './data/jobs.db'

def get_keywords(text):
    nlp = ml()
    doc = nlp(text)
    multis, singles = keywords(doc)

def ids2sql(ids):
    con = sqlite3.connect('./data/jobs.db')
    query = 'select details from jobs where '
    id_query = [f'id = {id}' for id in ids]
    split_queries = [query + ' or '.join(id_query[i : i + 200]) for i in range(0, len(id_query), 200)]
    data = []
    for query in split_queries:
        for row in con.execute(query):
            data.append(row[0])

    con.close()
    return data

def details_from_db(data):
    texts = []
    for text in data:
        text = [t.encode('utf-8').decode('utf-8') for t in text.split('\n')]
        interest_lines = []
        for line in text:
            collect = False
            #start collecting lines from job details when skills section has reached
            if re.search('\\b(skills?|responsibilit(y|ies)|qualifications?|degrees?|experience):?\\b', line, re.IGNORECASE):
                collect = True
            #attempts to skip lines near the end of the table
            if re.search('to apply|cover letter|[a-z0-9]+@[a-z0-9]+', line, re.IGNORECASE): # stop collecting keywords when the last few lines have been reached
                collect = False

            if collect:
                interest_lines.append(line)

        texts.append(interest_lines)
    
    return texts

def extract(texts):
    # varies the structure of the text to a 2d list so it can be parsed
    if type(texts) == str:
        texts = [[texts]]
    elif type(texts) == list:
        if type(texts[0]) == str:
            texts = [texts]

    nlp = ml()
    kws = {}
    for text in texts:
        for line in text:
            doc = nlp(line)
            multis, singles = keywords(doc)
            for w in multis + singles:
                if kws.get(w) == None:
                    kws[w] = 1
                else:
                    kws[w] += 1

    kwlist = list(kws.items())
    sorted_kwlist = sorted(kwlist, key=lambda x: x[1])
    no_of_kws = sum([e[1] for e in sorted_kwlist])
    if no_of_kws < 5:
        return [e[:-1] for e in kwlist]
    else:
        return [e[: -1] for e in sorted_kwlist]

def ml():
    nlp = spacy.load('en_core_web_md')
    nlp.enable_pipe('senter')
    return nlp

def visualise(doc):
    for sentence in doc.sents:
        table = {}
        for w in sentence:
            cols = ['word', 'pos', 'tag', 'dep', 'morph', 'parent', 'entity', 'index',]
            vals = [w, w.pos_, [w.tag_, spacy.explain(w.tag_)], [w.dep_, spacy.explain(w.dep_)], w.morph, w.head, w.ent_type_, w.idx,]
            for c, v in zip(cols, vals):
                try:
                    table[c] += [v]
                except:
                    table[c] = [v]

        df = pd.DataFrame(table)
        print(df)

def keywords(doc, version=1):
    # look for most important word in sentence
    tag = ['NNP', 'NN', 'NNS', 'NNPS']
    dep = ['dobj', 'nsubj', 'ROOT', 'attr']
    main_words = []

    if version == 1:
        for _, w in enumerate(doc):
            if w.tag_ in tag:
                main_words.append([w, 0])
                for i, c in enumerate(dep):
                    if w.dep_ == c:
                        priority = i - len(dep)
                        main_words[-1][1] += 1
    
    if version == 2:
        for _, w in enumerate(doc):
            if w.tag_ in tag:
                for i, c in enumerate(dep):
                    if w.dep_ == c:
                        priority = i - len(dep)
                        main_words.append([w, priority])
    
    main_words = sorted(main_words, key=lambda x:x[1])
    # include any connectors or adjectives just in front of word
    multis = []
    singles = main_words.copy()
    for word in main_words:
        for child in word[0].children:
            # determine if any words in the main list should be joined to another to form a short phrase
            if child.dep_ in ['compound'] and word[0].idx == child.idx + len(child) + 1:
                multis.append([child, *word])
    
    # remove words from singles that appear in multis 
    for words in multis:
        for word in words[: -1]:
            for e in singles:
                if e[0] == word:
                    singles.remove(e)

    # merge multis if they overlap
    # create contiguous list of multis
    contiguous_multis = []
    for words in multis:
        for word in words[:-1]:
            contiguous_multis.append(word)
    # find words with multiple occurences
    long_multis = []
    copy_of_multis = multis.copy()
    for i, w in enumerate(contiguous_multis):
        if i == len(contiguous_multis) - 1:
            break
        elif w in contiguous_multis[i + 1:]:
            # locate all phrases that contain the same word
            to_combine = []
            for words in multis:
                for word in words[:-1]:
                    if word == w:
                        to_combine.append(words)
                        #remove these from the original multis list
                        copy_of_multis.remove(words)
            
            #create a contiguous list for to combined phrases
            cont_to_combine = []
            priority = 0
            for words in to_combine:
                for w in words[:-1]:
                    cont_to_combine.append(w)
                
                priority += words[-1]

            #merge and order the list of to be combined
            temp_list = list(set(cont_to_combine))
            combined_phrase = sorted(temp_list, key= lambda x: x.idx)
            long_multis.append(combined_phrase + [priority])

    all_multis = long_multis + copy_of_multis
    # remove priorities from word groups and join multi words into single phrases
    # also converts all token objects into strings
    singles_out = [w[0].lemma_ for w in singles]
    multis_out = []
    for w in all_multis:
        out = [word.lemma_ for word in w[: -1]]
        multis_out.append(' '.join(out))

    return multis_out, singles_out


if __name__ == '__main__':
    with open('../profiles/tony/resume/tech/resume.txt', 'r') as f:
        sample_text = []
        for line in f:
            sample_text.append(line)
    print(extract(sample_text))