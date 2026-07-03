import pdfplumber  #for pdfs
import BeautifulSoup  #for HTML

from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions 
from docling.datamodel.base_models import InputFormat
import pathlib, zipfile, logging
# (Lightweight alt: fitz (PyMuPDF), pdfplumber, pytesseract, docx, openpyxl/pandas)


