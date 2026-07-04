import pdfplumber  #for pdfs
from bs4 import BeautifulSoup
from typing import Any
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions 
from docling.datamodel.base_models import InputFormat
import pathlib, zipfile, logging
# (Lightweight alt: fitz (PyMuPDF), pdfplumber, pytesseract, docx, openpyxl/pandas)


