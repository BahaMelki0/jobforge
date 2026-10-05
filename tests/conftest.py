import os
os.environ.setdefault('JOBFORGE_DB_URL','sqlite:///./test_jobforge.db')
os.environ.setdefault('JOBFORGE_LLM_PROVIDER','none')
os.environ.setdefault('JOBFORGE_AUTO_REFRESH','false')
