"""Small, reproducible local drafting benchmark. Outputs stay on this machine.
Run: python scripts/benchmark_local_ai.py --models qwen3.5:4b qwen3.5:9b
"""
import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db import SessionLocal
from app.models import CandidateProfile
from app.schemas import MessageRequest
from app.services.llm import LLMService,model_status

JOBS={
 'soc':SimpleNamespace(title='Analyste SOC junior',company='Example SOC',location='Lyon, France',requirements="Debutant accepte. Bases reseaux, Windows et Linux. Aucune certification obligatoire.",description="Surveiller les alertes SIEM, qualifier les incidents et documenter les investigations avec une equipe senior. Formation interne a Sentinel et aux procedures SOC. Francais professionnel et anglais technique."),
 'support':SimpleNamespace(title='Technicien support informatique junior',company='Example Support',location='Paris, France',requirements="0 a 2 ans d'experience. Windows, Microsoft 365, Active Directory, sens du service.",description="Assurer le support utilisateurs N1, traiter les tickets, preparer les postes Windows et accompagner les utilisateurs de Microsoft 365. Escalader les incidents reseau complexes. CDI en France."),
 'network':SimpleNamespace(title='Administrateur reseaux junior',company='Example Networks',location='Rennes, France',requirements="Junior accepte. TCP/IP, DNS, DHCP, Linux. Une certification CCNA serait un plus mais n'est pas obligatoire.",description="Participer a la supervision des reseaux, au diagnostic de connectivite et a la documentation des configurations. Etre accompagne par un administrateur senior. Ne pas inventer de certification CCNA pour le candidat."),
 'offsec':SimpleNamespace(title='Junior Penetration Tester',company='Example Security',location='Paris, France',requirements='Graduate or 0-2 years. Active Directory, Python and basic web testing. OSCP preferred, not mandatory.',description='Assist senior testers with authorized security assessments, document findings and communicate remediation. Experience from internships and personal projects is accepted. Do not claim certifications absent from the candidate profile.')
}
CASES=[('soc','message','recruiter_message','fr'),('support','message','email_body','fr'),('network','message','connection_note','fr'),('offsec','message','recruiter_message','en'),('offsec','analysis',None,None),('soc','application',None,None)]


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--models',nargs='+',required=True);parser.add_argument('--roles',nargs='+',choices=list(JOBS));parser.add_argument('--wait',action='store_true');parser.add_argument('--output',default='runtime/ai-benchmark.json');args=parser.parse_args()
 out=[];path=Path(args.output);path.parent.mkdir(exist_ok=True,parents=True)
 with SessionLocal() as db:profile=db.scalar(select(CandidateProfile))
 for model in args.models:
  while model not in model_status(force=True)['installed']:
   if not args.wait:raise SystemExit(f'Missing model: {model}')
   time.sleep(10)
  for role,kind,channel,language in CASES:
   if args.roles and role not in args.roles:continue
   llm=LLMService(model=model);started=time.monotonic()
   try:
    if kind=='message':value=llm.recruiter_messages(profile,JOBS[role],MessageRequest(channel=channel,language=language))
    elif kind=='analysis':value=llm.semantic_fit(profile,JOBS[role])
    else:value=llm.generate_application(profile,JOBS[role])
    row={'model':model,'role':role,'kind':kind,'channel':channel,'validated':True,'metrics':llm.metrics,'output':value}
   except Exception as exc:row={'model':model,'role':role,'kind':kind,'validated':False,'error':str(exc)}
   row['wall_seconds']=round(time.monotonic()-started,2);out.append(row)
   path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({k:v for k,v in row.items() if k not in ('output','metrics')}),flush=True)
if __name__=='__main__':main()
