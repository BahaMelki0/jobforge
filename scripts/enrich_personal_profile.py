"""Apply supplied owner facts after creating a restorable JSON profile backup."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db import SessionLocal
from app.models import CandidateProfile
from app.personal_profile import enrich

with SessionLocal() as db:
    profile = db.scalar(select(CandidateProfile).limit(1))
    if profile is None or profile.name.casefold() != 'bahaeddine melki':
        raise SystemExit('Expected owner profile was not found; no changes made.')
    backup = Path('runtime') / ('profile-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '.json')
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(json.dumps({column.name: getattr(profile, column.name) for column in profile.__table__.columns}, default=str, indent=2), encoding='utf-8')
    enrich(profile)
    db.commit()
    print('Profile enriched; original profile saved to', backup)
