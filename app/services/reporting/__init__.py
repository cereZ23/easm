"""
Reporting services for the EASM platform.

Exposes a client-facing PDF security report generator built purely with
ReportLab (no external system libraries, offline, Helvetica fonts only).
"""

from app.services.reporting.pdf_report import generate_scan_report

__all__ = ["generate_scan_report"]
