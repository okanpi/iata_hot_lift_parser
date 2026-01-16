#!/usr/bin/env python3
"""
IATA DISH HOT (Hand-Off Transmission) File Parser
Based on DISH Revision 23 Specification

HOT files contain BSP (Billing and Settlement Plan) data transmitted
from BSP to airlines for revenue accounting and reconciliation.

Author: Claude for Freebird Airlines
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal
import re


# =============================================================================
# RECORD TYPE DEFINITIONS - DISH Revision 23
# =============================================================================

@dataclass
class RecordSpec:
    """Specification for a field within a record"""
    name: str
    start: int  # 1-indexed position
    length: int
    data_type: str  # 'A' = Alpha, 'N' = Numeric, 'AN' = Alphanumeric, 'S' = Signed Numeric
    description: str = ""


# DISH HOT Record Specifications (136 bytes per record)
# Based on DISH Revision 23 specification
RECORD_SPECS = {
    # BFH01 - File Header
    'BFH01': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('bsp_code', 12, 2, 'A', 'BSP Country Code'),
        RecordSpec('file_date', 14, 6, 'N', 'File Creation Date YYMMDD'),
        RecordSpec('billing_period', 20, 6, 'N', 'Billing Period YYMMDD'),
        RecordSpec('process_date', 26, 6, 'N', 'Processing Date YYMMDD'),
        RecordSpec('dish_version', 32, 5, 'AN', 'DISH Version'),
        RecordSpec('file_type', 37, 4, 'A', 'File Type (PROD/TEST)'),
        RecordSpec('airline_code', 41, 3, 'AN', 'Airline Code'),
        RecordSpec('filler', 44, 93, 'A', 'Filler'),
    ],

    # BCH02 - Billing Analysis Header
    'BCH02': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('airline_code', 12, 3, 'AN', 'Airline Numeric Code'),
        RecordSpec('billing_period', 15, 6, 'N', 'Billing Period YYMMDD'),
        RecordSpec('bsp_code', 21, 2, 'A', 'BSP Code'),
        RecordSpec('currency', 23, 3, 'A', 'Currency Code'),
        RecordSpec('billing_type', 26, 2, 'AN', 'Billing Type'),
        RecordSpec('remittance_period', 28, 3, 'N', 'Remittance Period'),
        RecordSpec('filler', 31, 106, 'A', 'Filler'),
    ],

    # BOH03 - Office Header (Agent)
    'BOH03': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('agent_iata_number', 12, 8, 'AN', 'Agent IATA Number'),
        RecordSpec('agent_check_digit', 20, 1, 'N', 'Check Digit'),
        RecordSpec('agent_name', 21, 52, 'A', 'Agent Name'),
        RecordSpec('agent_city', 73, 3, 'A', 'Agent City Code'),
        RecordSpec('filler', 76, 61, 'A', 'Filler'),
    ],

    # BKT06 - Transaction Header
    'BKT06': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_code', 12, 4, 'A', 'Transaction Code'),
        RecordSpec('airline_code', 16, 3, 'AN', 'Airline Numeric Code'),
        RecordSpec('document_count', 19, 6, 'N', 'Document Count'),
        RecordSpec('filler', 25, 112, 'A', 'Filler'),
    ],

    # BKS24 - Ticket/Document Identification (CORRECTED positions per DISH Rev 23)
    'BKS24': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Transaction Sequence Number'),
        RecordSpec('document_number', 12, 14, 'AN', 'Ticket/Document Number'),
        RecordSpec('transaction_code', 26, 4, 'A', 'Transaction Code (TKTT/RFND/EXCH)'),
        RecordSpec('form_code', 30, 4, 'A', 'Form Code'),
        RecordSpec('issue_date', 34, 6, 'N', 'Date of Issue DDMMYY'),
        RecordSpec('original_issue_date', 40, 6, 'N', 'Date of Original Document DDMMYY'),
        RecordSpec('issue_time', 46, 6, 'N', 'Time of Issue HHMMSS'),
        RecordSpec('dom_int_indicator', 52, 1, 'A', 'Domestic/International (D/I)'),
        RecordSpec('tour_code', 53, 15, 'AN', 'Tour Code'),
        RecordSpec('related_doc_number', 68, 14, 'AN', 'Related Document Number'),
        RecordSpec('filler', 82, 55, 'A', 'Filler'),
    ],

    # BKS30 - STD/Document Amounts
    'BKS30': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('stat_code', 12, 1, 'A', 'Statistical Code'),
        RecordSpec('currency', 13, 3, 'A', 'Currency Code'),
        RecordSpec('currency_decimals', 16, 1, 'N', 'Currency Decimals'),
        RecordSpec('fare_amount', 17, 12, 'S', 'Fare Amount (signed)'),
        RecordSpec('equivalent_fare', 29, 12, 'S', 'Equivalent Fare Amount'),
        RecordSpec('total_tax', 41, 12, 'S', 'Total Tax Amount'),
        RecordSpec('penalty', 53, 12, 'S', 'Penalty Amount'),
        RecordSpec('total_amount', 65, 12, 'S', 'Total Document Amount'),
        RecordSpec('filler', 77, 60, 'A', 'Filler'),
    ],

    # BKS31 - Coupon Tax Information
    'BKS31': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('tax_country', 12, 2, 'A', 'Tax Country Code'),
        RecordSpec('tax_code_1', 14, 2, 'A', 'Tax Code 1'),
        RecordSpec('tax_amount_1', 16, 12, 'S', 'Tax Amount 1'),
        RecordSpec('tax_code_2', 28, 2, 'A', 'Tax Code 2'),
        RecordSpec('tax_amount_2', 30, 12, 'S', 'Tax Amount 2'),
        RecordSpec('tax_code_3', 42, 2, 'A', 'Tax Code 3'),
        RecordSpec('tax_amount_3', 44, 12, 'S', 'Tax Amount 3'),
        RecordSpec('tax_code_4', 56, 2, 'A', 'Tax Code 4'),
        RecordSpec('tax_amount_4', 58, 12, 'S', 'Tax Amount 4'),
        RecordSpec('filler', 70, 67, 'A', 'Filler'),
    ],

    # BKS39 - Commission Record
    'BKS39': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('comm_type', 12, 1, 'A', 'Commission Type'),
        RecordSpec('comm_rate', 13, 5, 'N', 'Commission Rate (x100)'),
        RecordSpec('comm_amount', 18, 12, 'S', 'Commission Amount'),
        RecordSpec('vat_on_comm', 30, 12, 'S', 'VAT on Commission'),
        RecordSpec('net_remit', 42, 12, 'S', 'Net Remittance Amount'),
        RecordSpec('filler', 54, 83, 'A', 'Filler'),
    ],

    # BKI63 - Itinerary Data Segment
    'BKI63': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('coupon_number', 12, 2, 'N', 'Coupon Number'),
        RecordSpec('origin', 14, 3, 'A', 'Origin Airport'),
        RecordSpec('destination', 17, 3, 'A', 'Destination Airport'),
        RecordSpec('stopover_code', 20, 1, 'A', 'Stopover Code (O/X)'),
        RecordSpec('carrier', 21, 3, 'AN', 'Operating Carrier Code'),
        RecordSpec('flight_number', 24, 5, 'AN', 'Flight Number'),
        RecordSpec('class_of_service', 29, 2, 'A', 'Class of Service'),
        RecordSpec('flight_date', 31, 6, 'N', 'Flight Date DDMMYY'),
        RecordSpec('departure_time', 37, 4, 'N', 'Departure Time HHMM'),
        RecordSpec('arrival_time', 41, 4, 'N', 'Arrival Time HHMM'),
        RecordSpec('fare_basis', 45, 15, 'AN', 'Fare Basis'),
        RecordSpec('nvb', 60, 6, 'N', 'Not Valid Before'),
        RecordSpec('nva', 66, 6, 'N', 'Not Valid After'),
        RecordSpec('baggage', 72, 3, 'AN', 'Free Baggage Allowance'),
        RecordSpec('coupon_value', 75, 12, 'S', 'Coupon Value'),
        RecordSpec('filler', 87, 50, 'A', 'Filler'),
    ],

    # BAR64 - Passenger Name
    'BAR64': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('passenger_name', 12, 49, 'A', 'Passenger Name (SURNAME/FIRSTNAME)'),
        RecordSpec('passenger_type', 61, 3, 'A', 'Passenger Type (ADT/CHD/INF)'),
        RecordSpec('filler', 64, 73, 'A', 'Filler'),
    ],

    # BKP84 - Form of Payment
    'BKP84': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('fop_sequence', 12, 2, 'N', 'FOP Sequence'),
        RecordSpec('fop_type', 14, 2, 'A', 'Form of Payment Type'),
        RecordSpec('cc_code', 16, 2, 'A', 'Credit Card Code'),
        RecordSpec('fop_amount', 18, 12, 'S', 'FOP Amount'),
        RecordSpec('card_number', 30, 20, 'AN', 'Card Number'),
        RecordSpec('expiry', 50, 4, 'N', 'Expiry MMYY'),
        RecordSpec('approval_code', 54, 8, 'AN', 'Approval Code'),
        RecordSpec('filler', 62, 75, 'A', 'Filler'),
    ],

    # BOT93 - Transaction Totals
    'BOT93': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_code', 12, 4, 'A', 'Transaction Code'),
        RecordSpec('currency', 16, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 19, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 25, 14, 'S', 'Total Fare'),
        RecordSpec('tax_total', 39, 14, 'S', 'Total Tax'),
        RecordSpec('penalty_total', 53, 14, 'S', 'Total Penalty'),
        RecordSpec('comm_total', 67, 14, 'S', 'Total Commission'),
        RecordSpec('net_remit_total', 81, 14, 'S', 'Net Remittance'),
        RecordSpec('total_amount', 95, 14, 'S', 'Total Amount'),
        RecordSpec('filler', 109, 28, 'A', 'Filler'),
    ],

    # BOT94 - Office Totals
    'BOT94': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('currency', 12, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 15, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 21, 14, 'S', 'Total Fare'),
        RecordSpec('tax_total', 35, 14, 'S', 'Total Tax'),
        RecordSpec('penalty_total', 49, 14, 'S', 'Total Penalty'),
        RecordSpec('comm_total', 63, 14, 'S', 'Total Commission'),
        RecordSpec('net_remit_total', 77, 14, 'S', 'Net Remittance'),
        RecordSpec('total_amount', 91, 14, 'S', 'Total Amount'),
        RecordSpec('filler', 105, 32, 'A', 'Filler'),
    ],

    # BCT95 - Billing Analysis Totals
    'BCT95': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('currency', 12, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 15, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 21, 14, 'S', 'Total Fare'),
        RecordSpec('tax_total', 35, 14, 'S', 'Total Tax'),
        RecordSpec('penalty_total', 49, 14, 'S', 'Total Penalty'),
        RecordSpec('comm_total', 63, 14, 'S', 'Total Commission'),
        RecordSpec('net_remit_total', 77, 14, 'S', 'Net Remittance'),
        RecordSpec('total_amount', 91, 14, 'S', 'Total Amount'),
        RecordSpec('filler', 105, 32, 'A', 'Filler'),
    ],

    # BFT99 - File Totals
    'BFT99': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('currency', 12, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 15, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 21, 14, 'S', 'Total Fare'),
        RecordSpec('tax_total', 35, 14, 'S', 'Total Tax'),
        RecordSpec('penalty_total', 49, 14, 'S', 'Total Penalty'),
        RecordSpec('comm_total', 63, 14, 'S', 'Total Commission'),
        RecordSpec('net_remit_total', 77, 14, 'S', 'Net Remittance'),
        RecordSpec('total_amount', 91, 14, 'S', 'Total Amount'),
        RecordSpec('filler', 105, 32, 'A', 'Filler'),
    ],
}


# =============================================================================
# DATA CLASSES FOR PARSED RECORDS
# =============================================================================

@dataclass
class TicketDocument:
    """Represents a complete ticket/document with all related records"""
    document_number: str = ""
    transaction_code: str = ""  # TKTT, RFND, EXCH
    form_code: str = ""
    issue_date: Optional[datetime] = None
    original_issue_date: Optional[datetime] = None
    dom_int_indicator: str = ""
    passenger_name: str = ""
    passenger_type: str = ""

    # Financial
    currency: str = ""
    currency_decimals: int = 2
    fare_amount: Decimal = Decimal('0')
    equivalent_fare: Decimal = Decimal('0')
    total_tax: Decimal = Decimal('0')
    penalty: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    commission_amount: Decimal = Decimal('0')
    commission_rate: Decimal = Decimal('0')
    net_remit: Decimal = Decimal('0')

    # Taxes breakdown
    taxes: List[Dict[str, Any]] = field(default_factory=list)

    # Itinerary
    segments: List[Dict[str, Any]] = field(default_factory=list)

    # Payment
    fop_type: str = ""
    fop_cc_code: str = ""
    card_number: str = ""
    fop_amount: Decimal = Decimal('0')

    # Raw data
    raw_records: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Agent:
    """Represents a travel agent/office"""
    iata_number: str = ""
    name: str = ""
    city: str = ""
    documents: List[TicketDocument] = field(default_factory=list)

    # Totals
    total_fare: Decimal = Decimal('0')
    total_tax: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    net_remit: Decimal = Decimal('0')
    document_count: int = 0


@dataclass
class HOTFile:
    """Represents a complete HOT file"""
    # File header info
    bsp_code: str = ""
    file_date: Optional[datetime] = None
    billing_period: str = ""
    dish_version: str = ""
    file_type: str = ""

    # Billing analysis
    airline_code: str = ""
    currency: str = ""

    # Agents and documents
    agents: List[Agent] = field(default_factory=list)

    # File totals
    total_documents: int = 0
    total_fare: Decimal = Decimal('0')
    total_tax: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    net_remit: Decimal = Decimal('0')

    # Raw records for debugging
    raw_records: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# PARSER CLASS
# =============================================================================

class HOTParser:
    """Parser for IATA DISH HOT files"""

    RECORD_LENGTH = 136

    # EBCDIC Overpunch mapping for signed fields
    # Positive: { = 0, A = 1, B = 2, C = 3, D = 4, E = 5, F = 6, G = 7, H = 8, I = 9
    # Negative: } = 0, J = 1, K = 2, L = 3, M = 4, N = 5, O = 6, P = 7, Q = 8, R = 9
    OVERPUNCH_POSITIVE = {'{': '0', 'A': '1', 'B': '2', 'C': '3', 'D': '4',
                          'E': '5', 'F': '6', 'G': '7', 'H': '8', 'I': '9'}
    OVERPUNCH_NEGATIVE = {'}': '0', 'J': '1', 'K': '2', 'L': '3', 'M': '4',
                          'N': '5', 'O': '6', 'P': '7', 'Q': '8', 'R': '9'}

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._currency_decimals = 2  # Default decimal places

    def parse_file(self, filepath: str) -> HOTFile:
        """Parse a HOT file and return structured data"""
        with open(filepath, 'rb') as f:
            content = f.read()
        # Try different encodings
        for encoding in ['latin-1', 'cp1252', 'utf-8', 'ascii']:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = content.decode('latin-1', errors='replace')
        return self.parse_content(text)

    def parse_content(self, content: str) -> HOTFile:
        """Parse HOT content string"""
        hot_file = HOTFile()

        # Handle both \n and \r\n line endings, and also fixed-width without line breaks
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        # Check if content has line breaks or is continuous
        if '\n' in content:
            lines = content.strip().split('\n')
        else:
            # Split by fixed record length
            lines = [content[i:i+self.RECORD_LENGTH]
                     for i in range(0, len(content), self.RECORD_LENGTH)]

        current_agent: Optional[Agent] = None
        current_document: Optional[TicketDocument] = None

        for line_num, line in enumerate(lines, 1):
            # Skip empty lines
            line = line.rstrip('\r\n')
            if not line or line.isspace():
                continue

            # Pad line to 136 characters if needed
            if len(line) < self.RECORD_LENGTH:
                line = line.ljust(self.RECORD_LENGTH)

            record_id = line[:5]

            # Skip unknown record types silently for common filler records
            if record_id.strip() == '' or record_id.startswith(' '):
                continue

            parsed = self._parse_record(line, record_id)

            if parsed is None:
                self.warnings.append(f"Line {line_num}: Unknown record type '{record_id}'")
                continue

            hot_file.raw_records.append(parsed)

            # Get the spec key for processing
            spec_key = parsed.get('_spec_key', record_id)
            prefix3 = record_id[:3]

            # Process based on record type (using prefix matching)
            if prefix3 == 'BFH':
                self._process_file_header(hot_file, parsed)

            elif prefix3 == 'BCH':
                self._process_billing_header(hot_file, parsed)

            elif prefix3 == 'BOH':
                # Save previous agent
                if current_document and current_agent:
                    current_agent.documents.append(current_document)
                    current_document = None
                if current_agent:
                    hot_file.agents.append(current_agent)
                # New agent
                current_agent = Agent()
                self._process_office_header(current_agent, parsed)

            elif prefix3 == 'BKT':
                # Transaction header - can be used for grouping
                pass

            elif prefix3 == 'BKS':
                # Determine BKS subtype from spec_key or content
                if spec_key == 'BKS24' or self._is_document_record(parsed):
                    # New document - save previous if exists
                    if current_document and current_agent:
                        current_agent.documents.append(current_document)
                    current_document = TicketDocument()
                    self._process_document_id(current_document, parsed)
                elif spec_key == 'BKS30' and current_document:
                    self._process_amounts(current_document, parsed)
                elif spec_key == 'BKS31' and current_document:
                    self._process_tax(current_document, parsed)
                elif spec_key == 'BKS39' and current_document:
                    self._process_commission(current_document, parsed)
                elif current_document:
                    # Try to auto-detect record type based on content
                    self._process_auto_bks(current_document, parsed)

            elif prefix3 == 'BKI' and current_document:
                self._process_segment(current_document, parsed)

            elif prefix3 == 'BAR' and current_document:
                # Could be passenger (BAR64) or FOP (BAR66)
                self._process_passenger(current_document, parsed)

            elif prefix3 == 'BKP' and current_document:
                self._process_payment(current_document, parsed)

            elif prefix3 == 'BKF' and current_document:
                # Fare calculation - treat like amounts if no amounts yet
                if current_document.total_amount == 0:
                    self._process_amounts(current_document, parsed)

            elif prefix3 == 'BOT':
                if current_agent:
                    # Save last document before processing totals
                    if current_document:
                        current_agent.documents.append(current_document)
                        current_document = None
                    self._process_office_totals(current_agent, parsed)

            elif prefix3 == 'BCT':
                # Billing analysis totals - informational
                pass

            elif prefix3 == 'BFT':
                # Save last agent before processing file totals
                if current_document and current_agent:
                    current_agent.documents.append(current_document)
                    current_document = None
                if current_agent:
                    hot_file.agents.append(current_agent)
                    current_agent = None
                self._process_file_totals(hot_file, parsed)

        # Add remaining document and agent
        if current_document and current_agent:
            current_agent.documents.append(current_document)
        if current_agent and current_agent not in hot_file.agents:
            hot_file.agents.append(current_agent)

        return hot_file

    # Mapping from record prefix to spec key
    RECORD_PREFIX_MAP = {
        'BFH': 'BFH01',  # File Header
        'BCH': 'BCH02',  # Billing Analysis Header
        'BOH': 'BOH03',  # Office Header
        'BKT': 'BKT06',  # Transaction Header
        'BKS24': 'BKS24',  # Document ID (check full 5 chars first)
        'BKS30': 'BKS30',  # Amounts
        'BKS31': 'BKS31',  # Tax
        'BKS39': 'BKS39',  # Commission
        'BKI': 'BKI63',  # Itinerary
        'BAR64': 'BAR64',  # Passenger
        'BAR66': 'BAR66',  # FOP Detail
        'BAR': 'BAR64',  # Default BAR to passenger
        'BKP': 'BKP84',  # Payment
        'BKF': 'BKS30',  # Fare record - treat like amounts
        'BOT93': 'BOT93',  # Transaction Totals
        'BOT94': 'BOT94',  # Office Totals
        'BOT': 'BOT94',  # Default BOT to office totals
        'BCT': 'BCT95',  # Billing Totals
        'BFT': 'BFT99',  # File Totals
    }

    def _get_spec_key(self, record_id: str) -> Optional[str]:
        """Get the specification key for a record ID using prefix matching"""
        # First try exact match
        if record_id in RECORD_SPECS:
            return record_id

        # Try full 5-char match in prefix map
        if record_id in self.RECORD_PREFIX_MAP:
            return self.RECORD_PREFIX_MAP[record_id]

        # Try 3-char prefix match
        prefix3 = record_id[:3]
        if prefix3 in self.RECORD_PREFIX_MAP:
            return self.RECORD_PREFIX_MAP[prefix3]

        # Special handling for BKS records - try to detect type from content
        if prefix3 == 'BKS':
            # Default to BKS24 for document records
            return 'BKS24'

        return None

    def _parse_record(self, line: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Parse a single record line based on its specification"""
        spec_key = self._get_spec_key(record_id)
        if spec_key is None or spec_key not in RECORD_SPECS:
            return None

        result = {'_record_id': record_id, '_spec_key': spec_key, '_raw': line}

        for spec in RECORD_SPECS[spec_key]:
            start = spec.start - 1  # Convert to 0-indexed
            end = start + spec.length
            raw_value = line[start:end] if end <= len(line) else line[start:]

            # Parse based on data type
            if spec.data_type == 'S':  # Signed numeric with overpunch
                result[spec.name] = self._parse_signed_numeric(raw_value)
            elif spec.data_type == 'N':
                result[spec.name] = self._parse_numeric(raw_value)
            else:
                result[spec.name] = raw_value.strip()

        return result

    def _is_document_record(self, parsed: Dict) -> bool:
        """Check if a BKS record is a document identification record"""
        # Check for document number pattern (typically has airline code + serial)
        doc_num = parsed.get('document_number', '')
        trans_code = parsed.get('transaction_code', '')
        # Document records usually have TKTT, RFND, EXCH, CANX etc
        if trans_code in ('TKTT', 'RFND', 'EXCH', 'CANX', 'ACMA', 'ADMA'):
            return True
        # Check if document number looks like a ticket number
        if doc_num and len(doc_num.strip()) >= 10:
            return True
        return False

    def _process_auto_bks(self, doc: 'TicketDocument', parsed: Dict):
        """Auto-detect and process BKS record based on content"""
        raw = parsed.get('_raw', '')

        # Try to detect record type from content patterns
        # If we see currency code at position 13-15, it's likely amounts (BKS30)
        if len(raw) > 15:
            potential_currency = raw[12:15].strip()
            if potential_currency.isalpha() and len(potential_currency) == 3:
                # Likely BKS30 (amounts)
                self._process_amounts(doc, parsed)
                return

        # If we see tax codes, it's BKS31
        if len(raw) > 16:
            potential_tax = raw[13:15].strip()
            if potential_tax in ('YQ', 'YR', 'TR', 'DE', 'GB', 'US', 'FR'):
                self._process_tax(doc, parsed)
                return

        # Default: try amounts
        doc.raw_records.append(parsed)

    def _parse_signed_numeric(self, value: str) -> Decimal:
        """Parse signed numeric field with EBCDIC overpunch convention"""
        value = value.strip()
        if not value:
            return Decimal('0')

        is_negative = False
        last_char = value[-1]

        # Check for overpunch sign in last character
        if last_char in self.OVERPUNCH_POSITIVE:
            value = value[:-1] + self.OVERPUNCH_POSITIVE[last_char]
            is_negative = False
        elif last_char in self.OVERPUNCH_NEGATIVE:
            value = value[:-1] + self.OVERPUNCH_NEGATIVE[last_char]
            is_negative = True
        # Also check for explicit +/- signs at end
        elif last_char == '+':
            value = value[:-1]
            is_negative = False
        elif last_char == '-':
            value = value[:-1]
            is_negative = True

        # Remove non-numeric
        value = re.sub(r'[^0-9]', '', value)

        if not value:
            return Decimal('0')

        try:
            # Apply decimal places (default 2)
            result = Decimal(value) / (10 ** self._currency_decimals)
            if is_negative:
                result = -result
            return result
        except Exception:
            return Decimal('0')

    def _parse_numeric(self, value: str) -> Any:
        """Parse unsigned numeric field"""
        value = value.strip()
        if not value:
            return 0

        # Remove non-numeric
        clean_value = re.sub(r'[^0-9]', '', value)

        if not clean_value:
            return 0

        try:
            return int(clean_value)
        except ValueError:
            return 0

    def _parse_date_ddmmyy(self, value: str) -> Optional[datetime]:
        """Parse date in DDMMYY format"""
        value = str(value).strip().zfill(6)
        if not value or len(value) != 6 or value == '000000':
            return None
        try:
            return datetime.strptime(value, '%d%m%y')
        except ValueError:
            # Try YYMMDD format as fallback
            try:
                return datetime.strptime(value, '%y%m%d')
            except ValueError:
                return None

    def _process_file_header(self, hot_file: HOTFile, record: Dict):
        hot_file.bsp_code = record.get('bsp_code', '')
        hot_file.file_date = self._parse_date_ddmmyy(record.get('file_date', ''))
        hot_file.billing_period = str(record.get('billing_period', ''))
        hot_file.dish_version = record.get('dish_version', '')
        hot_file.file_type = record.get('file_type', '')
        if record.get('airline_code'):
            hot_file.airline_code = record.get('airline_code', '')

    def _process_billing_header(self, hot_file: HOTFile, record: Dict):
        hot_file.airline_code = record.get('airline_code', '')
        hot_file.currency = record.get('currency', '')
        if not hot_file.bsp_code:
            hot_file.bsp_code = record.get('bsp_code', '')

    def _process_office_header(self, agent: Agent, record: Dict):
        agent.iata_number = record.get('agent_iata_number', '')
        agent.name = record.get('agent_name', '').strip()
        agent.city = record.get('agent_city', '')

    def _process_document_id(self, doc: TicketDocument, record: Dict):
        doc.document_number = record.get('document_number', '').strip()
        doc.transaction_code = record.get('transaction_code', '').strip()
        doc.form_code = record.get('form_code', '').strip()
        doc.issue_date = self._parse_date_ddmmyy(record.get('issue_date', ''))
        doc.original_issue_date = self._parse_date_ddmmyy(record.get('original_issue_date', ''))
        doc.dom_int_indicator = record.get('dom_int_indicator', '')
        doc.raw_records.append(record)

    def _process_amounts(self, doc: TicketDocument, record: Dict):
        doc.currency = record.get('currency', '').strip()

        # Get currency decimals if available
        decimals = record.get('currency_decimals', 2)
        if isinstance(decimals, int) and 0 <= decimals <= 4:
            doc.currency_decimals = decimals
            self._currency_decimals = decimals

        doc.fare_amount = record.get('fare_amount', Decimal('0'))
        doc.equivalent_fare = record.get('equivalent_fare', Decimal('0'))
        doc.total_tax = record.get('total_tax', Decimal('0'))
        doc.penalty = record.get('penalty', Decimal('0'))
        doc.total_amount = record.get('total_amount', Decimal('0'))
        doc.raw_records.append(record)

    def _process_tax(self, doc: TicketDocument, record: Dict):
        country = record.get('tax_country', '')

        # Process up to 4 tax codes per record
        for i in range(1, 5):
            tax_code = record.get(f'tax_code_{i}', '').strip()
            tax_amount = record.get(f'tax_amount_{i}', Decimal('0'))

            if tax_code and tax_amount != Decimal('0'):
                tax_info = {
                    'country': country,
                    'code': tax_code,
                    'amount': tax_amount,
                }
                doc.taxes.append(tax_info)

        doc.raw_records.append(record)

    def _process_commission(self, doc: TicketDocument, record: Dict):
        comm_rate = record.get('comm_rate', 0)
        if isinstance(comm_rate, int):
            doc.commission_rate = Decimal(comm_rate) / 100  # Convert from x100
        else:
            doc.commission_rate = Decimal('0')
        doc.commission_amount = record.get('comm_amount', Decimal('0'))
        doc.net_remit = record.get('net_remit', Decimal('0'))
        doc.raw_records.append(record)

    def _process_segment(self, doc: TicketDocument, record: Dict):
        segment = {
            'coupon': record.get('coupon_number', ''),
            'origin': record.get('origin', '').strip(),
            'destination': record.get('destination', '').strip(),
            'stopover': record.get('stopover_code', ''),
            'carrier': record.get('carrier', '').strip(),
            'flight_number': record.get('flight_number', '').strip(),
            'class': record.get('class_of_service', '').strip(),
            'flight_date': self._parse_date_ddmmyy(record.get('flight_date', '')),
            'departure_time': str(record.get('departure_time', '')).zfill(4),
            'arrival_time': str(record.get('arrival_time', '')).zfill(4),
            'fare_basis': record.get('fare_basis', '').strip(),
        }
        doc.segments.append(segment)
        doc.raw_records.append(record)

    def _process_passenger(self, doc: TicketDocument, record: Dict):
        doc.passenger_name = record.get('passenger_name', '').strip()
        doc.passenger_type = record.get('passenger_type', '').strip()
        doc.raw_records.append(record)

    def _process_payment(self, doc: TicketDocument, record: Dict):
        doc.fop_type = record.get('fop_type', '').strip()
        doc.fop_cc_code = record.get('cc_code', '').strip()
        doc.card_number = record.get('card_number', '').strip()
        doc.fop_amount = record.get('fop_amount', Decimal('0'))
        doc.raw_records.append(record)

    def _process_office_totals(self, agent: Agent, record: Dict):
        agent.document_count = record.get('document_count', 0)
        agent.total_fare = record.get('fare_total', Decimal('0'))
        agent.total_tax = record.get('tax_total', Decimal('0'))
        agent.total_amount = record.get('total_amount', Decimal('0'))
        agent.net_remit = record.get('net_remit_total', Decimal('0'))

    def _process_file_totals(self, hot_file: HOTFile, record: Dict):
        hot_file.currency = record.get('currency', '') or hot_file.currency
        hot_file.total_documents = record.get('document_count', 0)
        hot_file.total_fare = record.get('fare_total', Decimal('0'))
        hot_file.total_tax = record.get('tax_total', Decimal('0'))
        hot_file.total_amount = record.get('total_amount', Decimal('0'))
        hot_file.net_remit = record.get('net_remit_total', Decimal('0'))


# =============================================================================
# REPORTING / EXPORT FUNCTIONS
# =============================================================================

def generate_summary_report(hot_file: HOTFile) -> str:
    """Generate a human-readable summary report"""
    lines = []
    lines.append("=" * 70)
    lines.append("IATA HOT FILE SUMMARY REPORT")
    lines.append("=" * 70)
    lines.append("")

    # File Info
    lines.append("FILE INFORMATION")
    lines.append("-" * 40)
    lines.append(f"BSP Code:        {hot_file.bsp_code}")
    lines.append(f"File Date:       {hot_file.file_date.strftime('%d-%m-%Y') if hot_file.file_date else '-'}")
    lines.append(f"Billing Period:  {hot_file.billing_period}")
    lines.append(f"Airline Code:    {hot_file.airline_code}")
    lines.append(f"Currency:        {hot_file.currency}")
    lines.append(f"DISH Version:    {hot_file.dish_version}")
    lines.append(f"File Type:       {hot_file.file_type}")
    lines.append("")

    # File Totals
    lines.append("FILE TOTALS")
    lines.append("-" * 40)
    lines.append(f"Total Documents: {hot_file.total_documents}")
    lines.append(f"Total Fare:      {hot_file.currency} {hot_file.total_fare:,.2f}")
    lines.append(f"Total Tax:       {hot_file.currency} {hot_file.total_tax:,.2f}")
    lines.append(f"Total Amount:    {hot_file.currency} {hot_file.total_amount:,.2f}")
    lines.append(f"Net Remittance:  {hot_file.currency} {hot_file.net_remit:,.2f}")
    lines.append("")

    # Agents
    lines.append("AGENTS / OFFICES")
    lines.append("-" * 40)
    for agent in hot_file.agents:
        lines.append(f"\n  Agent: {agent.iata_number} - {agent.name} ({agent.city})")
        lines.append(f"  Documents: {len(agent.documents)}")
        lines.append(f"  Total Amount: {hot_file.currency} {agent.total_amount:,.2f}")

        # Documents
        for doc in agent.documents:
            lines.append(f"\n    Ticket: {doc.document_number}")
            lines.append(f"    Type: {doc.transaction_code} ({doc.form_code})")
            lines.append(f"    Passenger: {doc.passenger_name} ({doc.passenger_type})")
            lines.append(f"    Issue Date: {doc.issue_date.strftime('%d-%m-%Y') if doc.issue_date else '-'}")
            lines.append(f"    Dom/Int: {doc.dom_int_indicator}")
            lines.append(f"    Fare: {doc.currency} {doc.fare_amount:,.2f}")
            lines.append(f"    Tax: {doc.currency} {doc.total_tax:,.2f}")
            lines.append(f"    Total: {doc.currency} {doc.total_amount:,.2f}")
            lines.append(f"    Commission: {doc.commission_rate:.2%} ({doc.currency} {doc.commission_amount:,.2f})")
            lines.append(f"    Net Remit: {doc.currency} {doc.net_remit:,.2f}")
            lines.append(f"    Payment: {doc.fop_type} {doc.fop_cc_code} {doc.card_number}")

            # Itinerary
            if doc.segments:
                lines.append("    Itinerary:")
                for seg in doc.segments:
                    flight_date = seg['flight_date'].strftime('%d%b') if seg.get('flight_date') else ''
                    lines.append(f"      {seg['coupon']}: {seg['origin']}-{seg['destination']} "
                               f"{seg['carrier']}{seg['flight_number']} {seg['class']} "
                               f"{flight_date} {seg['departure_time']}-{seg['arrival_time']} "
                               f"({seg.get('fare_basis', '')})")

            # Taxes
            if doc.taxes:
                lines.append("    Taxes:")
                for tax in doc.taxes:
                    lines.append(f"      {tax['code']}: {doc.currency} {tax['amount']:,.2f} ({tax.get('country', '')})")

    lines.append("")
    lines.append("=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


def export_to_csv(hot_file: HOTFile, filepath: str):
    """Export documents to CSV format"""
    import csv

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'Agent_IATA', 'Agent_Name', 'Agent_City',
            'Document_Number', 'Transaction_Code', 'Form_Code', 'Issue_Date',
            'Passenger_Name', 'Passenger_Type', 'Dom_Int',
            'Currency', 'Fare', 'Tax', 'Penalty', 'Total',
            'Commission_Rate', 'Commission_Amount', 'Net_Remit',
            'FOP_Type', 'CC_Code', 'Card_Number',
            'Itinerary'
        ])

        # Data
        for agent in hot_file.agents:
            for doc in agent.documents:
                itinerary = ' / '.join([
                    f"{s.get('origin', '')}-{s.get('destination', '')}" for s in doc.segments
                ])

                writer.writerow([
                    agent.iata_number, agent.name, agent.city,
                    doc.document_number, doc.transaction_code, doc.form_code,
                    doc.issue_date.strftime('%Y-%m-%d') if doc.issue_date else '',
                    doc.passenger_name, doc.passenger_type, doc.dom_int_indicator,
                    doc.currency, float(doc.fare_amount), float(doc.total_tax),
                    float(doc.penalty), float(doc.total_amount),
                    float(doc.commission_rate), float(doc.commission_amount), float(doc.net_remit),
                    doc.fop_type, doc.fop_cc_code, doc.card_number,
                    itinerary
                ])


def export_to_json(hot_file: HOTFile, filepath: str):
    """Export to JSON format"""
    import json
    from decimal import Decimal

    class DecimalEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)

    data = {
        'file_info': {
            'bsp_code': hot_file.bsp_code,
            'file_date': hot_file.file_date,
            'billing_period': hot_file.billing_period,
            'airline_code': hot_file.airline_code,
            'currency': hot_file.currency,
            'dish_version': hot_file.dish_version,
            'file_type': hot_file.file_type,
        },
        'totals': {
            'documents': hot_file.total_documents,
            'fare': hot_file.total_fare,
            'tax': hot_file.total_tax,
            'total': hot_file.total_amount,
            'net_remit': hot_file.net_remit,
        },
        'agents': []
    }

    for agent in hot_file.agents:
        agent_data = {
            'iata_number': agent.iata_number,
            'name': agent.name,
            'city': agent.city,
            'totals': {
                'documents': agent.document_count,
                'fare': agent.total_fare,
                'tax': agent.total_tax,
                'total': agent.total_amount,
                'net_remit': agent.net_remit,
            },
            'documents': []
        }

        for doc in agent.documents:
            doc_data = {
                'document_number': doc.document_number,
                'transaction_code': doc.transaction_code,
                'form_code': doc.form_code,
                'issue_date': doc.issue_date,
                'dom_int': doc.dom_int_indicator,
                'passenger': {
                    'name': doc.passenger_name,
                    'type': doc.passenger_type,
                },
                'amounts': {
                    'currency': doc.currency,
                    'fare': doc.fare_amount,
                    'equivalent_fare': doc.equivalent_fare,
                    'tax': doc.total_tax,
                    'penalty': doc.penalty,
                    'total': doc.total_amount,
                },
                'commission': {
                    'rate': doc.commission_rate,
                    'amount': doc.commission_amount,
                    'net_remit': doc.net_remit,
                },
                'payment': {
                    'type': doc.fop_type,
                    'cc_code': doc.fop_cc_code,
                    'card_number': doc.card_number,
                    'amount': doc.fop_amount,
                },
                'itinerary': doc.segments,
                'taxes': doc.taxes,
            }
            agent_data['documents'].append(doc_data)

        data['agents'].append(agent_data)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, cls=DecimalEncoder, indent=2, ensure_ascii=False)


# =============================================================================
# MAIN / CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='IATA DISH HOT File Parser (Rev 23)')
    parser.add_argument('input', help='Input HOT file path')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('-f', '--format', choices=['report', 'csv', 'json'],
                        default='report', help='Output format')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')

    args = parser.parse_args()

    # Parse
    hot_parser = HOTParser(debug=args.debug)
    hot_file = hot_parser.parse_file(args.input)

    # Warnings
    if hot_parser.warnings:
        print("Warnings:")
        for w in hot_parser.warnings[:20]:  # Limit warnings shown
            print(f"  - {w}")
        if len(hot_parser.warnings) > 20:
            print(f"  ... and {len(hot_parser.warnings) - 20} more warnings")
        print()

    # Output
    if args.format == 'report':
        report = generate_summary_report(hot_file)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Report saved to: {args.output}")
        else:
            print(report)

    elif args.format == 'csv':
        output = args.output or 'hot_export.csv'
        export_to_csv(hot_file, output)
        print(f"CSV exported to: {output}")

    elif args.format == 'json':
        output = args.output or 'hot_export.json'
        export_to_json(hot_file, output)
        print(f"JSON exported to: {output}")


if __name__ == '__main__':
    main()
