# IATA HOT/LIFT Parser

Web-based parser for IATA DISH HOT (Hand-Off Transmission) and LIFT files used in BSP (Billing and Settlement Plan) airline revenue accounting.

## Features

- Parse HOT/LIFT files and display structured data
- View file information, totals, agents, and individual documents
- Export to JSON, CSV, or text report formats
- Modern drag-and-drop web interface
- Ready for Google Cloud Run deployment

## Local Development

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd iata_hot_lift_parser

# Install dependencies
pip install -r requirements.txt

# Run the development server
python app.py
```

Open http://localhost:8080 in your browser.

## Google Cloud Run Deployment

### Prerequisites

- Google Cloud account with billing enabled
- Google Cloud SDK installed and configured
- Docker (optional, for local testing)

### Quick Deploy

```bash
# Authenticate with Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com

# Deploy using Cloud Build
gcloud builds submit --config cloudbuild.yaml
```

### Manual Deploy

```bash
# Build and push the Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/iata-hot-parser

# Deploy to Cloud Run
gcloud run deploy iata-hot-parser \
  --image gcr.io/YOUR_PROJECT_ID/iata-hot-parser \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated
```

## Project Structure

```
iata_hot_lift_parser/
├── app.py              # Flask web application
├── hot_parser.py       # IATA HOT file parser
├── templates/
│   └── index.html      # Web interface
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container configuration
├── cloudbuild.yaml     # Cloud Build configuration
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/parse` | POST | Parse file, return JSON |
| `/parse/csv` | POST | Parse file, return CSV |
| `/parse/report` | POST | Parse file, return text report |
| `/health` | GET | Health check |

## Supported Record Types

- BFH01 - File Header
- BCH02 - Billing Analysis Header
- BOH03 - Office/Agent Header
- BKT06 - Transaction Header
- BKS24 - Ticket/Document Identification
- BKS30 - Document Amounts
- BKS31 - Tax Breakdown
- BKS39 - Commission
- BKI61 - Origin City
- BKI63 - Itinerary Segment
- BAR64 - Passenger Name
- BAR66 - Form of Payment
- BKP84 - Payment Information
- BOT93 - Transaction Totals
- BOT94 - Office Totals
- BCT95 - Billing Analysis Totals
- BFT99 - File Totals

## License

MIT License
