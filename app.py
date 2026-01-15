#!/usr/bin/env python3
"""
IATA HOT/LIFT Parser Web Application
Flask-based web interface for parsing IATA BSP files
"""

import os
import io
import csv
import json
from datetime import datetime
from decimal import Decimal
from flask import Flask, render_template, request, jsonify, Response

from hot_parser import HOTParser, HOTFile, generate_summary_report

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal and datetime types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def hot_file_to_dict(hot_file: HOTFile) -> dict:
    """Convert HOTFile dataclass to dictionary for JSON serialization"""
    return {
        'file_info': {
            'bsp_code': hot_file.bsp_code,
            'file_date': hot_file.file_date.isoformat() if hot_file.file_date else None,
            'billing_period': hot_file.billing_period,
            'airline_code': hot_file.airline_code,
            'currency': hot_file.currency,
            'dish_version': hot_file.dish_version,
            'file_type': hot_file.file_type,
        },
        'totals': {
            'documents': hot_file.total_documents,
            'fare': float(hot_file.total_fare),
            'tax': float(hot_file.total_tax),
            'total': float(hot_file.total_amount),
            'net_remit': float(hot_file.net_remit),
        },
        'agents': [
            {
                'iata_number': agent.iata_number,
                'name': agent.name,
                'city': agent.city,
                'totals': {
                    'documents': agent.document_count,
                    'fare': float(agent.total_fare),
                    'tax': float(agent.total_tax),
                    'total': float(agent.total_amount),
                    'net_remit': float(agent.net_remit),
                },
                'documents': [
                    {
                        'document_number': doc.document_number,
                        'transaction_code': doc.transaction_code,
                        'issue_date': doc.issue_date.isoformat() if doc.issue_date else None,
                        'passenger': {
                            'name': doc.passenger_name,
                            'type': doc.passenger_type,
                        },
                        'amounts': {
                            'currency': doc.currency,
                            'fare': float(doc.fare_amount),
                            'tax': float(doc.total_tax),
                            'penalty': float(doc.penalty),
                            'total': float(doc.total_amount),
                        },
                        'commission': {
                            'rate': float(doc.commission_rate),
                            'amount': float(doc.commission_amount),
                            'net_remit': float(doc.net_remit),
                        },
                        'payment': {
                            'type': doc.fop_type,
                            'card_type': doc.card_type,
                            'card_number': doc.card_number,
                        },
                        'itinerary': {
                            'origin': doc.origin_city,
                            'segments': [
                                {
                                    'coupon': seg.get('coupon', ''),
                                    'origin': seg.get('origin', ''),
                                    'destination': seg.get('destination', ''),
                                    'carrier': seg.get('carrier', ''),
                                    'class': seg.get('class', ''),
                                    'flight_date': seg['flight_date'].isoformat() if seg.get('flight_date') else None,
                                    'departure_time': seg.get('departure_time', ''),
                                    'arrival_time': seg.get('arrival_time', ''),
                                    'flight_number': seg.get('flight_number', ''),
                                }
                                for seg in doc.segments
                            ],
                        },
                        'taxes': [
                            {
                                'country': tax.get('country', ''),
                                'currency': tax.get('currency', ''),
                                'code': tax.get('code', ''),
                                'amount': float(tax.get('amount', 0)),
                            }
                            for tax in doc.taxes
                        ],
                    }
                    for doc in agent.documents
                ],
            }
            for agent in hot_file.agents
        ],
    }


def generate_csv_content(hot_file: HOTFile) -> str:
    """Generate CSV content from HOTFile"""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Agent_IATA', 'Agent_Name', 'Agent_City',
        'Document_Number', 'Transaction_Code', 'Issue_Date',
        'Passenger_Name', 'Passenger_Type',
        'Currency', 'Fare', 'Tax', 'Total', 'Commission_Rate', 'Commission_Amount', 'Net_Remit',
        'FOP_Type', 'Card_Type',
        'Origin', 'Itinerary'
    ])

    # Data
    for agent in hot_file.agents:
        for doc in agent.documents:
            itinerary = ' / '.join([
                f"{s.get('origin', '')}-{s.get('destination', '')}" for s in doc.segments
            ])

            writer.writerow([
                agent.iata_number, agent.name, agent.city,
                doc.document_number, doc.transaction_code,
                doc.issue_date.strftime('%Y-%m-%d') if doc.issue_date else '',
                doc.passenger_name, doc.passenger_type,
                doc.currency, float(doc.fare_amount), float(doc.total_tax), float(doc.total_amount),
                float(doc.commission_rate), float(doc.commission_amount), float(doc.net_remit),
                doc.fop_type, doc.card_type,
                doc.origin_city, itinerary
            ])

    return output.getvalue()


@app.route('/')
def index():
    """Main page with upload form"""
    return render_template('index.html')


@app.route('/parse', methods=['POST'])
def parse_file():
    """Parse uploaded HOT/LIFT file and return JSON"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Check file extension
    allowed_extensions = {'.hot', '.lift', '.txt'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

    try:
        # Read file content
        content = file.read().decode('latin-1')

        # Parse the file
        parser = HOTParser()
        hot_file = parser.parse_content(content)

        # Convert to dict
        result = hot_file_to_dict(hot_file)

        # Add parser warnings
        result['warnings'] = parser.warnings

        # Add filename
        result['filename'] = file.filename

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Parse error: {str(e)}'}), 500


@app.route('/parse/report', methods=['POST'])
def parse_file_report():
    """Parse uploaded file and return text report"""
    if 'file' not in request.files:
        return 'No file uploaded', 400

    file = request.files['file']

    if file.filename == '':
        return 'No file selected', 400

    try:
        content = file.read().decode('latin-1')
        parser = HOTParser()
        hot_file = parser.parse_content(content)
        report = generate_summary_report(hot_file)

        return Response(report, mimetype='text/plain')

    except Exception as e:
        return f'Parse error: {str(e)}', 500


@app.route('/parse/csv', methods=['POST'])
def parse_file_csv():
    """Parse uploaded file and return CSV"""
    if 'file' not in request.files:
        return 'No file uploaded', 400

    file = request.files['file']

    if file.filename == '':
        return 'No file selected', 400

    try:
        content = file.read().decode('latin-1')
        parser = HOTParser()
        hot_file = parser.parse_content(content)
        csv_content = generate_csv_content(hot_file)

        # Generate filename
        base_name = os.path.splitext(file.filename)[0]
        csv_filename = f'{base_name}_parsed.csv'

        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={csv_filename}'}
        )

    except Exception as e:
        return f'Parse error: {str(e)}', 500


@app.route('/health')
def health():
    """Health check endpoint for Cloud Run"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
