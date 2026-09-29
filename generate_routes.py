import os
names = ['health', 'rainfall', 'terrain', 'runoff', 'prediction', 'hazards', 'inundation', 'alerts', 'observations']
os.makedirs('backend/app/api/routes', exist_ok=True)
for name in names:
    with open(f'backend/app/api/routes/{name}.py', 'w') as f:
        f.write(f'from fastapi import APIRouter\n\nrouter = APIRouter()\n\n@router.get("/")\nasync def get_{name}():\n    return {{"status": "ok", "module": "{name}"}}\n')
open('backend/app/api/routes/__init__.py', 'w').close()
open('backend/app/api/__init__.py', 'w').close()
open('backend/app/__init__.py', 'w').close()
