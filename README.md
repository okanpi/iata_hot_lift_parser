# IATA HOT/LIFT Parser

A web-based application for parsing and analyzing IATA BSP (Billing and Settlement Plan) HOT (Hand-Off Transmission) and LIFT files following the DISH Revision 23 specification.

## Features

- **File Parsing**: Parse HOT/LIFT files with support for all standard record types
- **Web Interface**: Modern dark-themed drag-and-drop file upload UI
- **Multiple Export Formats**: JSON, CSV, and text report exports
- **Agent/Document Breakdown**: View detailed information by travel agent and document
- **Financial Summaries**: Fare, tax, commission, and net remittance totals

## Supported Record Types

| Record | Description |
|--------|-------------|
| BFH01 | File Header |
| BCH02 | Billing Analysis Header |
| BOH03 | Office Header (Agent Info) |
| BKT06 | Transaction Header |
| BKS24 | Document Identification |
| BKS30 | Document Amounts |
| BKS31 | Tax Breakdown |
| BKS39 | Commission Information |
| BKI61 | Origin City |
| BKI63 | Itinerary Segment |
| BAR64 | Passenger Information |
| BAR66 | Payment Information |
| BOT94 | Office Totals |
| BFT99 | File Totals |

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

# Open http://localhost:5000 in your browser
```

### Docker

```bash
# Build the image
docker build -t iata-hot-parser .

# Run the container
docker run -p 8080:8080 iata-hot-parser

# Open http://localhost:8080 in your browser
```

### Google Cloud Run Deployment

```bash
# Set your project ID
export GOOGLE_CLOUD_PROJECT=your-project-id

# Deploy
./deploy.sh
```

Or use Cloud Build:

```bash
gcloud builds submit --config cloudbuild.yaml
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/parse` | POST | Parse file, return JSON |
| `/parse/csv` | POST | Parse file, return CSV |
| `/parse/report` | POST | Parse file, return text report |
| `/health` | GET | Health check |

## Project Structure

```
iata_hot_lift_parser/
├── app.py              # Flask web application
├── hot_parser.py       # IATA HOT/LIFT parser module
├── templates/
│   └── index.html      # Web UI template
├── samples/
│   ├── sample.hot      # Sample HOT file
│   └── sample_multi.hot # Multi-agent sample
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container configuration
├── cloudbuild.yaml     # Google Cloud Build config
├── deploy.sh           # Deployment script
└── README.md           # This file
```

## Technology Stack

- **Backend**: Python 3.11, Flask 3.0
- **Frontend**: HTML5, CSS3, JavaScript
- **Deployment**: Docker, Google Cloud Run
- **Data Processing**: Python dataclasses, Decimal for financial precision

## License

See [LICENSE](LICENSE) file.
