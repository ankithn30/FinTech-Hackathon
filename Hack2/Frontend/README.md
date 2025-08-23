# Document Upload Frontend

A modern, responsive web interface for uploading documents with support for both single and multiple file uploads.

## Features

### 🎯 Single Document Upload
- Upload one document at a time
- Supports PDF, DOC, and DOCX files
- Drag and drop functionality
- File validation and preview
- Progress tracking

### 📚 Multiple Documents Upload
- Upload multiple documents simultaneously
- Batch processing support
- Individual file management
- Bulk upload with progress tracking

### ✨ User Experience
- Modern, responsive design
- Drag and drop file uploads
- Visual feedback and progress bars
- File type validation
- Error handling and status messages
- Mobile-friendly interface

## File Support

The interface accepts the following file types:
- **PDF** (.pdf) - Portable Document Format
- **DOC** (.doc) - Microsoft Word Document
- **DOCX** (.docx) - Microsoft Word Open XML Document

## How to Use

### Single Document Upload
1. Click on the "Single Document" section
2. Either:
   - Click the upload area to browse and select a file, or
   - Drag and drop a file onto the upload area
3. Review the selected file information
4. Click "Upload Single Document" to proceed
5. Monitor the upload progress
6. View the success/error status message

### Multiple Documents Upload
1. Click on the "Multiple Documents" section
2. Either:
   - Click the upload area to browse and select multiple files, or
   - Drag and drop multiple files onto the upload area
3. Review the selected files list
4. Remove any unwanted files using the "Remove" button
5. Click "Upload Multiple Documents" to proceed
6. Monitor the batch upload progress
7. View the success/error status message

### File Management
- **Remove Files**: Click the "Remove" button next to any file to remove it from the selection
- **File Preview**: See file name and size before uploading
- **Validation**: Invalid file types will show error messages

## Technical Details

### Frontend Technologies
- **HTML5**: Semantic markup structure
- **CSS3**: Modern styling with gradients, shadows, and animations
- **JavaScript**: Interactive functionality and file handling
- **Responsive Design**: Mobile-first approach with CSS Grid and Flexbox

### Browser Compatibility
- Chrome (recommended)
- Firefox
- Safari
- Edge
- Mobile browsers (iOS Safari, Chrome Mobile)

### File Handling
- **Drag & Drop**: Native HTML5 drag and drop API
- **File Validation**: Client-side file type checking
- **Progress Simulation**: Visual feedback during upload process
- **Error Handling**: User-friendly error messages

## Customization

### Styling
The interface uses CSS custom properties and can be easily customized:
- Color scheme in CSS variables
- Typography and spacing
- Border radius and shadows
- Animation timing

### Functionality
- File type restrictions can be modified in the `isValidFile()` function
- Upload behavior can be customized in the upload functions
- Progress bar styling and timing can be adjusted

## Integration

This frontend is designed to work with backend systems that can handle:
- File uploads via HTTP POST requests
- Multiple file processing
- File type validation
- Progress tracking
- Error handling and response

## Browser Support

- **Modern Browsers**: Full functionality
- **Legacy Browsers**: Basic functionality (fallback to file input)
- **Mobile**: Touch-friendly interface with responsive design

## Performance

- Lightweight JavaScript (no external dependencies)
- Optimized CSS with minimal repaints
- Efficient file handling and validation
- Responsive animations and transitions

## Security Considerations

- Client-side file type validation
- File size display for user awareness
- Secure file handling practices
- Input sanitization and validation

## Future Enhancements

Potential improvements could include:
- Real-time file upload to backend servers
- File compression and optimization
- Advanced file preview capabilities
- Cloud storage integration
- User authentication and file management
- Upload history and file tracking
