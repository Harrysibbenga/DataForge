# DataForge

A powerful data conversion tool that allows you to seamlessly transform between various data formats (CSV, JSON, Excel, XML, YAML) with advanced data cleaning and transformation capabilities.

![DataForge Logo](https://via.placeholder.com/800x200?text=DataForge)

## Features

- **Multiple Format Support**: Convert between CSV, JSON, Excel, XML, and YAML with a single click
- **Intelligent Data Cleaning**: Automatically transform your data with powerful cleaning operations
- **Modern Web Interface**: User-friendly interface with drag-and-drop file uploads
- **Developer-Ready API**: Complete REST API for programmatic access and integration
- **Data Transformation Pipeline**: Apply customizable transformations to your data
- **Batch Processing**: Handle multiple files efficiently (coming soon)

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/dataforge.git
cd dataforge

# Build and run with Docker Compose
docker-compose up -d

# Access the web interface at http://localhost:8000
```

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/dataforge.git
cd dataforge

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Access the web interface at http://localhost:8000
```

## Project Structure

```
dataforge/
│
├── app/                      # Main application package
│   ├── api/                  # API endpoints and routes
│   ├── core/                 # Core business logic
│   ├── models/               # Data models and schemas
│   ├── static/               # Static assets (CSS, JS)
│   └── templates/            # HTML templates
│
├── tests/                    # Test directory
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Docker compose configuration
├── main.py                   # Application entry point
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

## API Usage

### Convert a File

```bash
curl -X POST "http://localhost:8000/api/convert" \
-F "file=@your_file.csv" \
-F "to_format=json" \
-F "remove_empty_rows_flag=true" \
-F "standardize_names_flag=true" \
> output.json
```

### Get Supported Formats

```bash
curl -X GET "http://localhost:8000/api/formats"
```

## Available Transformations

| Transformation | Description |
|----------------|-------------|
| Remove Empty Rows | Eliminate rows where all values are empty |
| Remove Empty Columns | Remove columns with no data |
| Standardize Column Names | Convert column names to lowercase with underscores |
| Trim Whitespace | Remove excess spaces from text data |
| De-duplicate Rows | Remove duplicate entries |

## Pricing Plans

| Plan | Price | Features |
|------|-------|----------|
| Basic | Free | 5 conversions per day, 5MB file limit |
| Pro | $9.99/mo | 100 conversions per day, 50MB file limit |
| Enterprise | $24.99/mo | Unlimited conversions, 500MB file limit |

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, contact support@dataforge.io or open an issue on GitHub.