"""
IATA HOT/LIFT Parser - Flask Web Application
"""

import os
import io
import csv
from datetime import datetime
from decimal import Decimal
from flask import Flask, request, render_template, jsonify, make_response

from hot_parser import parse_hot_file, hot_file_to_dict, HOTFile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload


class CustomJSONEncoder:
    """Custom encoder for Decimal and datetime types"""
    @staticmethod
    def encode(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')


@app.route('/parse', methods=['POST'])
def parse_file():
    """Parse uploaded HOT/LIFT file and return JSON"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Read file content
        content = file.read().decode('utf-8', errors='replace')

        # Parse the file
        hot_file = parse_hot_file(content)

        # Convert to dict for JSON response
        result = hot_file_to_dict(hot_file)
        result['filename'] = file.filename

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/parse/csv', methods=['POST'])
def parse_file_csv():
    """Parse uploaded file and return CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        content = file.read().decode('utf-8', errors='replace')
        hot_file = parse_hot_file(content)

        # Create CSV output
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            'Agent IATA', 'Agent Name', 'Agent City',
            'Document Number', 'Transaction Type', 'Issue Date',
            'Passenger Name', 'Passenger Type',
            'Origin', 'Destination', 'Routing',
            'Fare', 'Tax', 'Penalty', 'Total',
            'Commission Rate', 'Commission Amount', 'Net Remittance',
            'FOP Type', 'Card Type', 'Card Number'
        ])

        # Data rows
        for agent in hot_file.agents:
            for doc in agent.documents:
                # Build routing string
                routing = doc.origin_city
                for seg in doc.itinerary:
                    if seg.destination:
                        routing += f"-{seg.destination}"
                if not routing and doc.destination_city:
                    routing = f"{doc.origin_city}-{doc.destination_city}"

                writer.writerow([
                    agent.iata_number, agent.name, agent.city,
                    doc.document_number, doc.transaction_code, doc.issue_date,
                    doc.passenger_name, doc.passenger_type,
                    doc.origin_city, doc.destination_city, routing,
                    str(doc.fare_amount), str(doc.tax_amount),
                    str(doc.penalty_amount), str(doc.total_amount),
                    str(doc.commission_rate), str(doc.commission_amount),
                    str(doc.net_remittance),
                    doc.fop_type, doc.card_type, doc.card_number
                ])

        # Create response
        csv_content = output.getvalue()
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = \
            f'attachment; filename={os.path.splitext(file.filename)[0]}.csv'

        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/parse/report', methods=['POST'])
def parse_file_report():
    """Parse uploaded file and return text report"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        content = file.read().decode('utf-8', errors='replace')
        hot_file = parse_hot_file(content)

        # Generate text report
        report = generate_report(hot_file, file.filename)

        response = make_response(report)
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = \
            f'attachment; filename={os.path.splitext(file.filename)[0]}_report.txt'

        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_report(hot_file: HOTFile, filename: str) -> str:
    """Generate human-readable text report"""
    lines = []
    lines.append("=" * 80)
    lines.append("IATA HOT/LIFT FILE ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append("")

    # File info
    lines.append("FILE INFORMATION")
    lines.append("-" * 40)
    lines.append(f"  Filename:        {filename}")
    lines.append(f"  BSP Code:        {hot_file.bsp_code}")
    lines.append(f"  Airline Code:    {hot_file.airline_code}")
    lines.append(f"  File Date:       {hot_file.file_date}")
    lines.append(f"  Billing Period:  {hot_file.billing_period}")
    lines.append(f"  Currency:        {hot_file.currency_code}")
    lines.append(f"  DISH Version:    {hot_file.dish_version}")
    lines.append(f"  File Type:       {hot_file.file_type}")
    lines.append("")

    # Summary totals
    lines.append("FILE TOTALS")
    lines.append("-" * 40)
    lines.append(f"  Total Documents: {hot_file.total_documents}")
    lines.append(f"  Total Fare:      {hot_file.currency_code} {hot_file.total_fare:,.2f}")
    lines.append(f"  Total Tax:       {hot_file.currency_code} {hot_file.total_tax:,.2f}")
    lines.append(f"  Total Amount:    {hot_file.currency_code} {hot_file.total_amount:,.2f}")
    lines.append(f"  Net Remittance:  {hot_file.currency_code} {hot_file.total_net_remit:,.2f}")
    lines.append("")

    # Agent details
    lines.append("=" * 80)
    lines.append("AGENT DETAILS")
    lines.append("=" * 80)

    for i, agent in enumerate(hot_file.agents, 1):
        lines.append("")
        lines.append(f"AGENT {i}: {agent.iata_number}")
        lines.append("-" * 60)
        lines.append(f"  Name:      {agent.name}")
        lines.append(f"  City:      {agent.city}")
        lines.append(f"  Country:   {agent.country}")
        lines.append(f"  Documents: {len(agent.documents)}")
        lines.append(f"  Fare:      {hot_file.currency_code} {agent.total_fare:,.2f}")
        lines.append(f"  Tax:       {hot_file.currency_code} {agent.total_tax:,.2f}")
        lines.append(f"  Total:     {hot_file.currency_code} {agent.total_amount:,.2f}")
        lines.append(f"  Net Remit: {hot_file.currency_code} {agent.total_net_remit:,.2f}")
        lines.append("")

        # Document list
        if agent.documents:
            lines.append("  DOCUMENTS:")
            lines.append("  " + "-" * 56)
            for doc in agent.documents:
                # Build routing
                routing = doc.origin_city
                for seg in doc.itinerary:
                    if seg.destination:
                        routing += f"-{seg.destination}"
                if not routing:
                    routing = f"{doc.origin_city}-{doc.destination_city}" if doc.destination_city else doc.origin_city

                lines.append(f"    Doc: {doc.document_number}  Type: {doc.transaction_code}")
                lines.append(f"    Passenger: {doc.passenger_name}")
                lines.append(f"    Issue Date: {doc.issue_date}  Routing: {routing}")
                lines.append(f"    Fare: {doc.fare_amount:,.2f}  Tax: {doc.tax_amount:,.2f}  "
                           f"Total: {doc.total_amount:,.2f}")
                if doc.commission_amount:
                    lines.append(f"    Commission: {doc.commission_rate}%  "
                               f"Amount: {doc.commission_amount:,.2f}  "
                               f"Net: {doc.net_remittance:,.2f}")
                if doc.fop_type:
                    fop_desc = {
                        'CA': 'Cash', 'CC': 'Credit Card', 'CK': 'Check',
                        'MS': 'Misc', 'IN': 'Invoice'
                    }.get(doc.fop_type, doc.fop_type)
                    payment = f"    Payment: {fop_desc}"
                    if doc.card_type:
                        payment += f" ({doc.card_type})"
                    if doc.card_number:
                        payment += f" {doc.card_number}"
                    lines.append(payment)
                lines.append("")

    # Warnings and errors
    if hot_file.warnings or hot_file.errors:
        lines.append("=" * 80)
        lines.append("PARSING NOTES")
        lines.append("=" * 80)
        if hot_file.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in hot_file.warnings[:20]:  # Limit to 20
                lines.append(f"  - {warning}")
        if hot_file.errors:
            lines.append("")
            lines.append("Errors:")
            for error in hot_file.errors[:20]:
                lines.append(f"  - {error}")

    lines.append("")
    lines.append("=" * 80)
    lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)

    return "\n".join(lines)


@app.route('/health')
def health():
    """Health check endpoint for Cloud Run"""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
