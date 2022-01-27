import yake

def extract(text):
    yk = yake.KeywordExtractor()
    kws = yk.extract_keywords(text)
    kws = [kw[0] for kw in kws][:3]
    return kws

if __name__ == '__main__':
    print(extract('you must possess a degree in finance'))
