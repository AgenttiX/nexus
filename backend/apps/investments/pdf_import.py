"""Importing prices and asset values from the PDF reports of banks and investing companies.

PLACEHOLDER. Each company lays out its reports differently, so the readers
will be written against example reports. The plan:

- Extract text and tables with ``pdfplumber`` (MIT licence). PyMuPDF is not an
  option, as its AGPL licence does not fit this project.
- One reader per report type, registered by company like the CSV importers in
  ``apps.finance.importers``.
- A report yields, per position, the asset (matched by ISIN or name), the
  quantity and the value on the report date. Values of assets that have no
  market price source (for example pension insurance) are stored as price
  points of an asset with a manual provider, which does not exist yet.
"""
