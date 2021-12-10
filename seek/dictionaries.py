from json.decoder import JSONDecodeError
import requests

def merriam_webster(w):
    key_used = 0
    keys = ['2181863b-1231-465b-84f2-db16c8853fa1', 'b1366550-3d40-4f7c-b53d-46c13eb246ab']
    dictionary_types = ['collegiate', 'sd3']
    url = "https://dictionaryapi.com/api/v3/references/" + dictionary_types[key_used] + '/json/' + w + '?key=' + keys[key_used]
    r = requests.get(url)
    try:
        r.raise_for_status()
    except:
        return 'No Definitions Found'
    try:
        a = r.json()
    except:
        raise Exception(r.text)

    if a == []: 
        return 'No Definitions Found'
    if type(a[0]) == str: 
        return 'No Definitions Found'
    else:
        return a[0]['fl']
    
def free_dictionary(w):

    w.replace(' ', '%20')
    r = requests.get(' https://api.dictionaryapi.dev/api/v2/entries/en/' + w)
    try:
        r.raise_for_status()
    except:
        return 'No Definitions Found'
    
    a = r.json()
    try:
        output = a[0]['meanings'][0]['partOfSpeech']
    except:
        output = 'No Definitions Found'
    
    return output

if '__main__' == __name__:
    word = 'services industry?'
    print(merriam_webster(word))
    print(free_dictionary(word))
