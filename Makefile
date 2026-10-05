.PHONY: run test docker demo clean

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

docker:
	docker compose up --build

demo:
	python -c "from app.db import Base,engine,SessionLocal; from app.seed import ensure_seed_data; from app.services.ingest import run_all_sources; from app.services.ranking import rank_job,save_score; from app.models import CandidateProfile,Job; from sqlalchemy import select; Base.metadata.create_all(engine); db=SessionLocal(); ensure_seed_data(db); print(run_all_sources(db)); p=db.scalar(select(CandidateProfile)); jobs=db.scalars(select(Job)).all(); [save_score(db,j,rank_job(p,j)) for j in jobs]; print([(j.title,j.score.total if j.score else None) for j in jobs])"

clean:
	rm -f jobforge.db test_jobforge.db
	rm -rf generated_applications .pytest_cache
