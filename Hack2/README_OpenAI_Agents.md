# OpenAI Two-Agent System for Form Filling

This document describes the new OpenAI-powered two-agent system that has been integrated into the FIFA (Financial Form Filling Agent) application.

## Overview

The system consists of two specialized AI agents that work together to extract data from documents and fill PDF forms:

1. **Extraction Agent**: Uses OpenAI GPT-4o-mini to extract structured data from documents
2. **Form Filling Agent**: Uses OpenAI GPT-4o-mini to intelligently map extracted data to PDF form fields

## Architecture

```
Document(s) → Extraction Agent → JSON Data → Form Filling Agent → Filled PDF(s)
```

### Key Components

- `openai_extraction_agent.py`: Handles document text extraction and data structuring
- `openai_form_filling_agent.py`: Manages form field mapping and PDF filling
- `openai_agent_coordinator.py`: Coordinates the workflow between both agents
- Updated Flask routes in `app.py`: Provides web API endpoints

## Features

### Extraction Agent Features
- **Multi-format Support**: Extracts text from PDF documents using PyMuPDF
- **Structured Output**: Returns data in organized JSON format with categories:
  - Personal Information (name, DOB, SSN, phone, email)
  - Address Information (current, previous, mailing addresses)
  - Employment Information (employer, job title, income)
  - Financial Information (bank details, assets, liabilities)
  - Document Metadata (type, date, reference numbers)
- **Batch Processing**: Can process multiple documents and combine results
- **Data Persistence**: Saves extracted data to JSON files for later use

### Form Filling Agent Features
- **Intelligent Field Mapping**: Uses AI to semantically match extracted data to form fields
- **Form Field Discovery**: Automatically detects all fillable fields in PDF forms
- **Confidence Scoring**: Provides confidence levels for field mappings
- **Preview Mode**: Shows how data will be mapped before actual filling
- **Batch Form Filling**: Can fill multiple forms with the same extracted data

### Coordinator Features
- **Complete Workflow Management**: Handles end-to-end process from documents to filled forms
- **Error Handling**: Robust error handling with detailed reporting
- **Progress Tracking**: Monitors and reports workflow progress
- **ZIP Archive Creation**: Packages multiple filled forms for easy download

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements_openai.txt
```

### 2. Set OpenAI API Key

Set your OpenAI API key as an environment variable:

```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

Or create a `.env` file in the project root:

```
OPENAI_API_KEY=your-openai-api-key-here
```

### 3. Verify Installation

Run the test script to verify everything is working:

```bash
python -c "from openai_agent_coordinator import OpenAIAgentCoordinator; print('✅ OpenAI agents ready!')"
```

## API Endpoints

The following new endpoints have been added to the Flask application:

### Single Document Extraction
- **POST** `/openai-extract`
- Extracts data from a single document using OpenAI
- Returns structured JSON data

### Single Form Filling
- **POST** `/openai-fill-form`
- Fills a single PDF form with previously extracted data
- Returns filled PDF for download

### Batch Processing
- **POST** `/openai-batch-process`
- Complete workflow: extract from multiple documents, fill multiple forms
- Returns ZIP file with all filled forms

### Field Mapping Preview
- **POST** `/openai-preview-mapping`
- Preview how extracted data will be mapped to form fields
- Returns mapping preview without actually filling the form

## Usage Examples

### 1. Extract Data from Document

```python
from openai_extraction_agent import OpenAIExtractionAgent

# Initialize agent
agent = OpenAIExtractionAgent()

# Extract data from a document
result = agent.extract_from_document("path/to/document.pdf")

if result["success"]:
    print(f"Extracted {result['extraction_summary']['total_fields']} fields")
    print(f"Data saved to: {result['json_file_path']}")
```

### 2. Fill Form with Extracted Data

```python
from openai_form_filling_agent import OpenAIFormFillingAgent

# Initialize agent
agent = OpenAIFormFillingAgent()

# Fill form using extracted data
result = agent.fill_form_from_json("path/to/form.pdf", "path/to/extracted_data.json")

if result["success"]:
    print(f"Form filled successfully: {result['output_pdf']}")
    print(f"Fields mapped: {result['fields_mapped']}/{result['total_form_fields']}")
```

### 3. Complete Two-Agent Workflow

```python
from openai_agent_coordinator import OpenAIAgentCoordinator

# Initialize coordinator
coordinator = OpenAIAgentCoordinator()

# Run complete workflow
result = coordinator.extract_and_fill_workflow(
    document_paths=["doc1.pdf", "doc2.pdf"],
    form_paths=["form1.pdf", "form2.pdf"]
)

if result["success"]:
    print(f"Workflow completed in {result['workflow_summary']['workflow_duration_seconds']} seconds")
    print(f"Forms filled: {result['workflow_summary']['successful_form_fills']}")
```

## Frontend Integration

The existing frontend (`Frontend/index.html`) is fully compatible with the new system. The JavaScript code automatically detects when OpenAI API is available and can use either the legacy system or the new OpenAI agents.

### Frontend Features
- **Automatic Fallback**: Uses OpenAI agents when available, falls back to legacy system
- **Progress Indicators**: Shows real-time progress for extraction and form filling
- **Error Handling**: Displays helpful error messages for API issues
- **Data Preview**: Shows extracted data before form filling
- **Batch Processing**: Supports multiple documents and forms

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: Model to use (default: "gpt-4o-mini")
- `OPENAI_MAX_TOKENS`: Maximum tokens per request (default: 2000)

### Customization

You can customize the extraction schema by modifying the `create_extraction_prompt` method in `openai_extraction_agent.py`:

```python
def create_extraction_prompt(self, document_text: str, extraction_schema: Optional[Dict] = None) -> str:
    # Add your custom fields here
    custom_fields = """
    - Custom Field 1: Description
    - Custom Field 2: Description
    """
    # ... rest of the method
```

## Performance Considerations

### Cost Optimization
- Uses GPT-4o-mini for cost-effective processing
- Limits input text to 8000 characters to control token usage
- Processes documents in batches to minimize API calls

### Speed Optimization
- Parallel processing for multiple forms
- Caches extracted data to avoid re-processing
- Uses efficient PDF processing with PyMuPDF

### Accuracy Optimization
- Low temperature (0.1) for consistent results
- Structured prompts with clear instructions
- Confidence scoring for field mappings
- Preview mode to verify mappings before filling

## Error Handling

The system includes comprehensive error handling:

- **API Errors**: Handles OpenAI API rate limits and errors
- **File Errors**: Manages file I/O issues and cleanup
- **Processing Errors**: Graceful handling of PDF processing failures
- **Validation Errors**: Checks for required fields and data formats

## Troubleshooting

### Common Issues

1. **"OpenAI API key not configured"**
   - Set the `OPENAI_API_KEY` environment variable
   - Verify the key is valid and has sufficient credits

2. **"No form fields found in PDF"**
   - Ensure the PDF has fillable form fields
   - Try using a different PDF form

3. **"Extraction failed"**
   - Check if the document contains readable text
   - Verify the PDF is not corrupted or password-protected

4. **"Form filling failed"**
   - Ensure extracted data contains relevant information
   - Check if form fields are compatible with extracted data types

### Debug Mode

Enable debug logging to see detailed processing information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Comparison with Legacy System

| Feature | Legacy System | OpenAI Two-Agent System |
|---------|---------------|-------------------------|
| Data Extraction | LlamaParse + Rule-based | OpenAI GPT-4o-mini |
| Field Mapping | Pattern matching | Semantic AI mapping |
| Accuracy | Good for structured docs | Excellent for all doc types |
| Flexibility | Limited to predefined patterns | Adapts to any document format |
| Cost | LlamaParse API costs | OpenAI API costs |
| Speed | Fast for simple docs | Moderate (API dependent) |
| Customization | Requires code changes | Natural language instructions |

## Future Enhancements

Planned improvements for the two-agent system:

1. **Multi-language Support**: Extract data from documents in different languages
2. **Custom Field Types**: Support for specialized field types (dates, currencies, etc.)
3. **Validation Rules**: AI-powered validation of extracted data
4. **Learning System**: Improve accuracy based on user feedback
5. **OCR Integration**: Handle scanned documents and images
6. **Workflow Templates**: Pre-configured workflows for common use cases

## Support

For issues or questions about the OpenAI two-agent system:

1. Check the troubleshooting section above
2. Review the error logs for detailed information
3. Ensure your OpenAI API key has sufficient credits
4. Verify all dependencies are installed correctly

## License

This OpenAI integration maintains the same license as the main FIFA project.
