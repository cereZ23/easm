"""
Enrichment tasks - to be implemented in Sprint 2

Will include:
- run_httpx: HTTP probing and tech detection
- run_naabu: Port scanning
- run_tlsx: TLS certificate intelligence
- run_katana: Web crawling
"""

from app.celery_app import celery

# Placeholder tasks for Sprint 2
@celery.task(name='app.tasks.enrichment.run_httpx')
def run_httpx(tenant_id: int, asset_ids: list = None):
    """HTTP probing - to be implemented in Sprint 2"""
    pass

@celery.task(name='app.tasks.enrichment.run_naabu')
def run_naabu(tenant_id: int, asset_ids: list = None, full_scan: bool = False):
    """Port scanning - to be implemented in Sprint 2"""
    pass

@celery.task(name='app.tasks.enrichment.run_tlsx')
def run_tlsx(tenant_id: int, asset_ids: list = None):
    """TLS intelligence - to be implemented in Sprint 2"""
    pass

@celery.task(name='app.tasks.enrichment.run_katana')
def run_katana(tenant_id: int):
    """Web crawling - to be implemented in Sprint 2"""
    pass
