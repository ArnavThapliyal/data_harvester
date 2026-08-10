# System Overview

## Purpose
The Data Harvester is an end-to-end pipeline for building per-company knowledge files from Indian equity market data. It collects both numeric financial data and document data, transforming everything into unified, source-linked markdown knowledge files.

## Core Components

### 1. Data Sources
- **Company Universe**: Nifty Midcap and Smallcap company universe maintained in `config/company_universe.csv`
- **Company Metadata**: URLs and metadata for each company in `config/company_urls.json`

### 2. Data Collection
- **Numeric Data**: API-based collectors for structured financial data (YFinance, NSE, BSE, Screener, IndiaAPI)
- **Document Data**: Web crawler for unstructured company documents (PDFs, HTML, etc.)

### 3. Data Processing Pipeline
- **Converter Chain**: Cleaner → Chunker → Embedder → Normalizer → Exporter (in progress)
- **Storage**: LanceDB for vector storage

### 4. Orchestration
- **Main Entry Point**: `main.py` orchestrates the entire pipeline with resumability and logging

## Architecture
The system follows a modular, stage-based architecture where each component is designed to be:
- **Deterministic**: Consistent outputs given the same inputs
- **Resumable**: Can continue from where it left off
- **Incremental**: Supports partial updates
- **Traceable**: Full provenance metadata maintained

## Current Implementation Status
The system is partially complete with:
- Complete orchestrator (`main.py`)
- Document crawler implementation 
- Numeric collectors (YFinance, NSE, BSE, Screener, IndiaAPI)
- Converter pipeline stages (cleaner, chunker, embedder, normalizer)
- Registry system for collectors
- Complete directory structure and configuration

The remaining work is focused on:
- Completing the document crawler (already implemented)
- Finalizing the exporter stage
- Creating company metadata files