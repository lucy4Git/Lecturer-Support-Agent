from __future__ import annotations
import json, py_compile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
required=[
'services/database/models/operations.py','services/api/app/schemas/department_operations.py',
'services/api/app/services/department_operations.py','services/api/app/routes/department_operations.py',
'services/database/migrations/versions/20260725_0006_v19_department_operations.py',
'tests/unit/test_v19_department_operations.py','docs/implementation/PHASE_8_V1.9_IMPLEMENTATION_REPORT.md',
'docs/api/V1.9_DEPARTMENT_OPERATIONS_API.md','docs/operations/V1.9_OWNER_MACHINE_VALIDATION.md',
'docs/architecture/adr/ADR-013-DEPARTMENTAL-TEACHING-OPERATIONS.md',
]
missing=[x for x in required if not (ROOT/x).exists()]
if missing: raise SystemExit('Missing required files: '+', '.join(missing))
for rel in required:
    if rel.endswith('.py'): py_compile.compile(str(ROOT/rel), doraise=True)
cat=json.loads((ROOT/'services/database/seeds/role_permissions.json').read_text())
perms={x['code'] for x in cat['permissions']}
expected={'academic_calendar.read','academic_calendar.manage','teaching_plans.read','teaching_plans.manage','module_readiness.read','module_readiness.manage','workload.read_own','workload.manage','handover.read','handover.manage','handover.accept','department.operations.read'}
assert expected <= perms
from services.database.models import Base
assert len(Base.metadata.tables)>=88
from services.api.app.main import app
paths={getattr(r,'path','') for r in app.routes}
assert '/api/v1/department-operations/dashboards/departments/{organisational_unit_id}' in paths
print(f'v1.9 release validation passed: {len(Base.metadata.tables)} cumulative tables, departmental operations routes, permissions, migration, tests, and documentation present.')
