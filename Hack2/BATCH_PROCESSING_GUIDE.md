# FinTech Batch Processing System

## Overview

The FinTech Batch Processing System allows you to process bulk documents and automatically fill multiple forms in parallel. This system implements the complete workflow:

**Documents & Forms → Main Agent → Sub-agents (Parallel Schema Generation) → Schema Compilation → LlamaParse API → JSON Data → PDF Writing Program (Parallel PDF Filling) → Final Filled Forms**

## Quick Start

### 1. Setup Folder Structure

Create the following folders in your `Hack2` directory:

```
Hack2/
├── Documents/          # Put your source documents here (PDFs)
├── Forms/             # Put your blank forms here (PDFs)
└── BatchOutput/       # Output will be generated here (auto-created)
```

### 2. Add Your Files

- **Documents folder**: Add PDF documents containing the data you want to extract (invoices, contracts, applications, etc.)
- **Forms folder**: Add blank PDF forms that you want to fill with the extracted data

### 3. Run Batch Processing

#### Option A: Simple Run (Recommended)
```bash
cd Hack2
python3 run_batch_processing.py
```

#### Option B: Advanced Run with Custom Paths
```bash
cd Hack2
python3 batch_processor.py --documents /path/to/docs --forms /path/to/forms --output /path/to/output
```

## System Architecture

### Complete Workflow

1. **Document Discovery**: Automatically finds all PDF files in Documents and Forms folders
2. **Main Agent Initialization**: Creates 5 sub-agents for parallel processing
3. **Parallel Document Processing**: Sub-agents extract schemas from documents simultaneously
4. **Schema Compilation**: All extracted schemas are merged into a unified schema
5. **Validation Engine**: Applies 3-tier validation (auto-approve, auto-validate, human review)
6. **Parallel Form Filling**: Multiple forms are filled simultaneously using extracted data
7. **Report Generation**: Comprehensive processing report with statistics and results

### Key Features

- **Parallel Processing**: Both document analysis and form filling run in parallel
- **Intelligent Field Mapping**: Advanced field matching including Unicode support
- **Validation Engine**: 3-tier validation system with confidence scoring
- **Comprehensive Logging**: Detailed logs and reports for audit trails
- **Error Handling**: Robust error handling with fallback mechanisms
- **Scalable**: Handles bulk processing efficiently

## Output Structure

After processing, you'll find:

```
BatchOutput/
├── filled_forms/              # Your completed forms
│   ├── filled_form1_20240824_120000.pdf
│   ├── filled_form2_20240824_120001.pdf
│   └── ...
├── processing_logs/           # Detailed processing logs
│   └── workflow_results_20240824_120000.json
├── validation_reports/        # Validation results
└── batch_report_20240824_120000.json  # Main report
```

## Configuration Options

### Command Line Arguments

```bash
python3 batch_processor.py [OPTIONS]

Options:
  -d, --documents PATH    Documents folder path (default: Documents)
  -f, --forms PATH       Forms folder path (default: Forms)  
  -o, --output PATH      Output folder path (default: BatchOutput)
  -h, --help            Show help message
```

### Environment Variables

Set these in your `.env` file:

```bash
LLAMA_CLOUD_API_KEY=your_api_key_here
```

## Supported File Types

- **Input**: PDF files only
- **Output**: PDF files with filled forms

## Performance

- **Parallel Sub-Agents**: Up to 5 documents processed simultaneously
- **Parallel Form Filling**: Up to 5 forms filled simultaneously
- **Processing Speed**: Depends on document complexity and API response times
- **Memory Usage**: Optimized for large batch processing

## Validation System

### 3-Tier Validation

1. **Tier 1 - Auto Approval (>98% confidence)**
   - High confidence extractions are automatically approved
   - No human intervention required

2. **Tier 2 - Auto Validation (90-98% confidence)**
   - Medium confidence extractions go through business rule validation
   - Automatically approved if rules pass

3. **Tier 3 - Human Review (<90% confidence or critical fields)**
   - Low confidence extractions flagged for human review
   - Critical fields (SSN, amounts, legal declarations) always require review

### Business Rules

- Invoice total validation
- Date format validation  
- Numeric field validation
- Required field validation

## Troubleshooting

### Common Issues

1. **No documents found**
   - Ensure Documents folder exists and contains PDF files
   - Check file permissions

2. **No forms found**
   - Ensure Forms folder exists and contains PDF forms
   - Verify forms have fillable fields (AcroForm)

3. **Form filling fails**
   - Check if PDF forms have proper field names
   - Ensure forms are fillable (not just images)
   - Verify field mapping in logs

4. **API errors**
   - Check LLAMA_CLOUD_API_KEY is set correctly
   - Verify internet connection
   - Check API rate limits

### Debug Mode

For detailed debugging:

```bash
cd Hack2
python3 debug_pdf_fields.py
```

This will analyze your PDF forms and show field mapping details.

## API Integration

### LlamaParse API
- Used for document text extraction
- Requires valid API key
- Handles various PDF formats

### Claude AI Integration
- Used for intelligent field extraction
- Provides confidence scoring
- Supports complex document analysis

## Security Considerations

- API keys are stored in environment variables
- Temporary files are cleaned up automatically
- Processing logs contain audit trails
- Validation ensures data integrity

## Performance Optimization

### For Large Batches

1. **Increase Worker Limits**: Modify `max_workers` in batch_processor.py
2. **Memory Management**: Process in smaller batches if memory issues occur
3. **API Rate Limits**: Add delays if hitting API limits
4. **Storage**: Ensure sufficient disk space for output files

### Monitoring

- Check batch reports for processing statistics
- Monitor error logs for issues
- Track validation rates for quality assessment

## Examples

### Example 1: Basic Usage

```bash
# Setup
mkdir Documents Forms
cp your_invoices.pdf Documents/
cp blank_form.pdf Forms/

# Run
python3 run_batch_processing.py
```

### Example 2: Custom Paths

```bash
python3 batch_processor.py \
  --documents /path/to/invoices \
  --forms /path/to/tax_forms \
  --output /path/to/completed_forms
```

### Example 3: Integration with Web App

The batch processor can also be used programmatically:

```python
from batch_processor import BatchProcessor

processor = BatchProcessor(
    documents_folder="my_docs",
    forms_folder="my_forms", 
    output_folder="results"
)

result = processor.run_batch_processing()
print(f"Processed {result['stats']['forms_filled']} forms")
```

## Support

For issues or questions:

1. Check the batch report for detailed error information
2. Run debug_pdf_fields.py to analyze form compatibility
3. Review processing logs in BatchOutput/processing_logs/
4. Check validation reports for data quality issues

## Version History

- **v1.0**: Initial batch processing system
- **v1.1**: Added parallel processing and validation engine
- **v1.2**: Enhanced field mapping and Unicode support
- **v1.3**: Added comprehensive reporting and error handling
