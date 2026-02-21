from rapidfuzz import process, fuzz
from job_scraper.utils.normalize import normalize_company_name
from job_scraper.utils.sponsor_loader import load_sponsor_lists

class SponsorChecker:
    def __init__(self):
        h1b, everify = load_sponsor_lists()
        
        self.h1b_list = h1b
        self.everify_list = everify

        self.h1b_set = set(h1b)
        self.everify_set = set(everify)

        self.h1b_found = {}
        self.everify_found = {}

    def check(self, company: str, threshold_sort=90, threshold_set=88):
        norm = normalize_company_name(company)
        if not norm:
            return {'h1b': False, 'everify': False}
        
        result = {}
        if norm in self.h1b_found:
            result['h1b'] = self.h1b_found[norm]
        else:
            h1b_result = self._match(norm, self.h1b_list, threshold_sort, threshold_set)
            self.h1b_found[norm] = h1b_result['match']
            result['h1b'] = h1b_result['match']

        if norm in self.everify_found:
            result['everify'] = self.everify_found[norm]
        else:   
            everify_result = self._match(norm, self.everify_list, threshold_sort, threshold_set)
            self.everify_found[norm] = everify_result['match']
            result['everify'] = everify_result['match']

        return result

    def _match(self, norm, keys, threshold_sort, threshold_set):
        # Layer 1: exact
        if keys is self.h1b_list and norm in self.h1b_set:
            return {'match': True, 'method': 'exact', 'score': 100}
        
        elif keys is self.everify_list and norm in self.everify_set:
            return {'match': True, 'method': 'exact', 'score': 100}
        
        elif keys is not self.h1b_list and keys is not self.everify_list:
            return {'match': False, 'method': 'incorrect', 'score': 0}
        
        # Layer 2: token sort
        r = process.extractOne(norm, keys, scorer=fuzz.token_sort_ratio, score_cutoff=threshold_sort)
        if r:
            return {'match': True, 'method': 'token_sort', 'score': r[1], 'matched': r[0]}

        # Layer 3: token set
        r = process.extractOne(norm, keys, scorer=fuzz.token_set_ratio, score_cutoff=threshold_set)
        if r:
            matched_is_single  = len(r[0].split()) == 1
            query_is_multi     = len(norm.split()) > 1
            if matched_is_single and query_is_multi:
                return {'match': False}  # reject: single key swallowing multi-word query

            if self._token_overlap_ok(norm, r[0]):
                return {'match': True, 'method': 'token_set', 'score': r[1], 'matched': r[0]}

        return {'match': False}

    def _token_overlap_ok(self, a: str, b: str, min_ratio=0.5, min_unique_score=60) -> bool:
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        shared   = tokens_a & tokens_b
        shorter  = min(len(tokens_a), len(tokens_b))

        if len(shared) / shorter < min_ratio:
            return False

        # the non-shared parts must also be somewhat similar
        unique_a = ' '.join(tokens_a - shared)
        unique_b = ' '.join(tokens_b - shared)
        if unique_a and unique_b:
            score = fuzz.ratio(unique_a, unique_b)
            if score < min_unique_score:
                return False

        return True