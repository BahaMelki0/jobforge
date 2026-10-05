"""Conservative, explainable France / junior eligibility, independent of AI."""
import re
import unicodedata


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').lower()) if not unicodedata.combining(c))


def has(text, pattern):
    return bool(re.search(pattern, plain(text)))


def target_role(title):
    t=plain(title)
    if re.search(r'agent de securite|incendie|securite industrielle|securite sociale|physical security|safety|supply chain|logistique|commercial|sales|account executive|business develop',t):
        return False
    return bool(re.search(r'appsec|devsecops|cyber|pentest|penetration|security|securite|\bsoc\b|\bsiem\b|\biam\b|\brssi\b|identity|identit|red.team|blue.team|incident.response|threat|detection|network|reseau|help.?desk|service.?desk|support (?:it|informatique|technique|utilisateur)|technicien informatique|desktop support|administrateur system|system.*administrator',t))


def required_years(value):
    t=plain(value)
    vals=[]
    # Require experience context; ignore company age, degrees and contract durations.
    for m in re.finditer(r'(\d{1,2})(?:\s*(?:-|–|a|to)\s*\d{1,2})?\s*\+?\s*(?:ans?|annees?|years?|yrs?)\b',t):
        before=t[max(0,m.start()-65):m.start()]
        after=t[m.end():m.end()+65]
        if not re.search(r'experience|experiences|working|professionnel',before+' '+after):
            continue
        if re.search(r'preferred|ideally|idealement|souhait|un plus',after):
            continue
        vals.append(int(m[1]))
    return max(vals) if vals else None


def assess(job):
    title=plain(job.title);loc=plain(job.location)
    description=' '.join([job.description or '',getattr(job,'requirements','') or ''])
    # Explicit country wins; a French-language page is never location evidence.
    foreign=r'\b(belgium|belgique|luxembourg|switzerland|suisse|germany|allemagne|united kingdom|united states|canada|tunisia|tunisie|morocco|maroc|spain|espagne|netherlands|london|brussels|bruxelles|geneva|geneve|montreal|berlin)\b'
    cities=r'\b(paris|lyon|marseille|toulouse|lille|bordeaux|nantes|rennes|strasbourg|nice|montpellier|grenoble|rouen|dijon|angers|brest|tours|orleans|metz|nancy|reims|clermont.ferrand|sophia.antipolis|valbonne|biot|courbevoie|puteaux|nanterre|palaiseau|saclay|lannion|limoges|saint.herblain|ile.de.france)\b'
    if re.search(foreign,loc):country='outside_france'
    elif re.search(r'\bfrance\b|(?:^|[, /])fr(?:$|[, /])',loc) or re.search(cities,loc):country='france'
    else:country='unknown'
    years=required_years(description)
    senior=bool(re.search(r'\b(senior|lead|leader|principal|manager|director|head|architecte?|confirme|experimente|responsable|expert)\b',title))
    junior=bool(re.search(r'\b(junior|graduate|debutant|entry.level|l1|n1|niveau 1)\b',title)) or bool(re.search(r'debutants? accept|jeunes? diplom|premiere experience|entry.level|graduates? welcome|junior profiles?|profil junior',plain(description)))
    training=bool(re.search(r'\b(stage|stagiaire|internship|intern|alternance|apprenticeship|apprenti)\b',title+' '+plain(getattr(job,'employment_type',''))))
    level='senior' if senior or (years is not None and years>2) else 'training' if training else 'junior' if junior or years is not None else 'unknown'
    reasons=[]
    if country!='france':reasons.append('Outside France' if country=='outside_france' else 'France location needs verification')
    if not target_role(title):reasons.append('Outside your target job families')
    if level=='senior':reasons.append(f'Requires {years}+ years' if years and years>2 else 'Senior or leadership title')
    if level=='unknown':reasons.append('Experience level not stated')
    if level=='training':reasons.append('Internship or apprenticeship')
    blocked=country=='outside_france' or level=='senior' or not target_role(title)
    status='excluded' if blocked else 'junior_france' if country=='france' and level=='junior' else 'training' if country=='france' and level=='training' else 'review'
    return {'status':status,'country':country,'level':level,'required_years':years,'reasons':reasons}


def cap_score(job,total):
    focus=assess(job)
    return min(total,39 if focus['status']=='excluded' else 69 if focus['status']=='review' else 100)
