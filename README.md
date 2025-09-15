# PDF Text Extractor App

A modern web application that extracts structured data from PDF documents using AI-powered LlamaCloud extraction services.

## Features

- **Drag & Drop PDF Upload**: Easy file upload with drag-and-drop support
- **AI-Powered Extraction**: Uses LlamaCloud's advanced AI to extract structured data
- **Custom Schema Builder**: Define your own extraction fields and data types
- **Beautiful UI**: Modern, responsive interface with Bootstrap and custom styling
- **JSON Export**: Download extracted data in structured JSON format
- **Real-time Processing**: Progress tracking and real-time feedback

## Prerequisites

- Python 3.8 or higher
- LlamaCloud API key (get one at [llama-cloud.com](https://llama-cloud.com))

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   - Copy `env_example.txt` to `.env`
   - Add your LlamaCloud API key:
     ```
     LLAMA_CLOUD_API_KEY=your_actual_api_key_here
     ```

4. **Create the uploads directory** (if it doesn't exist):
   ```bash
   mkdir uploads
   ```

## Usage

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and go to `http://localhost:5001`

3. **Upload a PDF**:
   - Drag and drop a PDF file onto the upload area, or
   - Click "Choose File" to browse and select a PDF

4. **View extracted data**:
   - The app will process your PDF and display the extracted structured data
   - You can download the results as JSON

5. **Customize extraction schema** (optional):
   - Use the Schema Builder to define custom fields
   - Add field names, types (string/list), and descriptions
   - Click "Update Schema" to apply changes

## Default Schema

The app comes with a default contact information extraction schema that looks for:
- **name**: Full name of person
- **phone_number**: Phone number
- **address**: Full address or location
- **email**: Email address

## Customization

### Adding Custom Fields

1. Use the Schema Builder section at the bottom of the page
2. Click "Add Field" to add new extraction fields
3. Define:
   - **Field Name**: The key for the extracted data
   - **Type**: String or List
   - **Description**: What the AI should look for in the PDF
4. Click "Update Schema" to save changes

### Modifying the Backend

The main extraction logic is in `app.py`. You can:
- Modify the default `Resume` schema class
- Add new extraction endpoints
- Customize error handling
- Add batch processing capabilities

## File Structure

```
Hack2/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Web interface
├── uploads/              # Temporary file storage
├── env_example.txt       # Environment variables template
└── README.md             # This file
```

## API Endpoints

- `GET /`: Main application interface
- `POST /upload`: Upload and extract PDF files
- `POST /custom-schema`: Update extraction schema

## Troubleshooting

### Common Issues

1. **"LLAMA_CLOUD_API_KEY environment variable not set"**
   - Make sure you have a `.env` file with your API key
   - Restart the application after adding the key

2. **"Invalid file type"**
   - Only PDF files are supported
   - Check that your file has a `.pdf` extension

3. **Extraction errors**
   - Verify your LlamaCloud API key is valid
   - Check that your PDF is readable and not corrupted
   - Ensure the PDF contains text (not just images)

### Getting Help

- Check the LlamaCloud documentation for API-related issues
- Verify your API key has sufficient credits/quota
- Test with a simple, text-based PDF first

## Security Notes

- The app temporarily stores uploaded files and deletes them after processing
- Change the `app.secret_key` in production
- Consider adding authentication for production use
- The uploads folder is created automatically and should not be exposed publicly

## License

This project is provided as-is for educational and development purposes.

## Contributing

Feel free to modify and improve this application for your specific needs!
