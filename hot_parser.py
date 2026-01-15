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
# RECORD TYPE DEFINITIONS
# =============================================================================

@dataclass
class RecordSpec:
    """Specification for a field within a record"""
    name: str
    start: int  # 1-indexed position
    length: int
    data_type: str  # 'A' = Alpha, 'N' = Numeric, 'AN' = Alphanumeric
    description: str = ""


# DISH HOT Record Specifications (136 bytes per record)
RECORD_SPECS = {
    # BFH01 - File Header
    'BFH01': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('bsp_code', 12, 2, 'A', 'BSP Country Code'),
        RecordSpec('file_date', 14, 8, 'N', 'File Creation Date YYYYMMDD'),
        RecordSpec('billing_period', 22, 8, 'N', 'Billing Period YYYYMMDD'),
        RecordSpec('process_date', 30, 8, 'N', 'Processing Date YYYYMMDD'),
        RecordSpec('dish_version', 38, 6, 'A', 'DISH Version'),
        RecordSpec('file_type', 44, 4, 'A', 'File Type (PROD/TEST)'),
        RecordSpec('filler', 48, 89, 'A', 'Filler'),
    ],

    # BCH02 - Billing Analysis Header
    'BCH02': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('airline_code', 12, 3, 'AN', 'Airline Numeric Code'),
        RecordSpec('billing_period', 15, 6, 'N', 'Billing Period YYYYMM'),
        RecordSpec('bsp_code', 21, 3, 'A', 'BSP Code'),
        RecordSpec('currency', 24, 3, 'A', 'Currency Code'),
        RecordSpec('billing_type', 27, 2, 'N', 'Billing Type'),
        RecordSpec('filler', 29, 108, 'A', 'Filler'),
    ],

    # BOH03 - Office Header (Agent)
    'BOH03': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('agent_iata_number', 12, 8, 'AN', 'Agent IATA Number'),
        RecordSpec('agent_name', 28, 40, 'A', 'Agent Name'),
        RecordSpec('agent_city', 68, 3, 'A', 'Agent City Code'),
        RecordSpec('filler', 71, 66, 'A', 'Filler'),
    ],

    # BKT06 - Transaction Header
    'BKT06': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('transaction_code', 18, 4, 'A', 'Transaction Code'),
        RecordSpec('airline_code', 22, 3, 'AN', 'Airline Numeric Code'),
        RecordSpec('document_count', 25, 7, 'N', 'Document Count'),
        RecordSpec('filler', 32, 105, 'A', 'Filler'),
    ],

    # BKS24 - Ticket/Document Identification
    'BKS24': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('document_number', 18, 14, 'AN', 'Ticket/Document Number'),
        RecordSpec('transaction_code', 32, 4, 'A', 'Transaction Code (TKTT/RFND/EXCH)'),
        RecordSpec('form_code', 36, 4, 'A', 'Form Code'),
        RecordSpec('issue_date', 40, 6, 'N', 'Date of Issue YYMMDD'),
        RecordSpec('original_issue_date', 46, 6, 'N', 'Original Issue Date YYMMDD'),
        RecordSpec('issue_time', 52, 6, 'N', 'Time of Issue HHMMSS'),
        RecordSpec('dom_int_indicator', 58, 1, 'A', 'Domestic/International (D/I)'),
        RecordSpec('filler', 59, 78, 'A', 'Filler'),
    ],

    # BKS30 - STD/Document Amounts
    'BKS30': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('currency', 18, 3, 'A', 'Currency Code'),
        RecordSpec('fare_amount', 21, 9, 'N', 'Fare Amount (with sign)'),
        RecordSpec('equivalent_fare', 30, 9, 'N', 'Equivalent Fare Amount'),
        RecordSpec('total_tax', 39, 9, 'N', 'Total Tax Amount'),
        RecordSpec('penalty', 48, 9, 'N', 'Penalty Amount'),
        RecordSpec('total_amount', 57, 9, 'N', 'Total Document Amount (with sign)'),
        RecordSpec('filler', 66, 71, 'A', 'Filler'),
    ],

    # BKS31 - Tax Breakdown
    'BKS31': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('tax_country', 18, 2, 'A', 'Tax Country Code'),
        RecordSpec('currency', 20, 3, 'A', 'Currency Code'),
        RecordSpec('tax_amount', 23, 12, 'N', 'Tax Amount (with sign)'),
        RecordSpec('tax_code', 35, 4, 'A', 'Tax Code (YQ, YR, etc.)'),
        RecordSpec('tax_amount_2', 39, 12, 'N', 'Tax Amount 2 (with sign)'),
        RecordSpec('filler', 51, 86, 'A', 'Filler'),
    ],

    # BKS39 - Commission
    'BKS39': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('comm_amount', 18, 11, 'N', 'Commission Amount'),
        RecordSpec('comm_rate', 29, 5, 'N', 'Commission Rate (x100)'),
        RecordSpec('net_remit', 34, 12, 'N', 'Net Remittance Amount (with sign)'),
        RecordSpec('filler', 46, 91, 'A', 'Filler'),
    ],

    # BKI61 - Origin City
    'BKI61': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('coupon_number', 18, 3, 'N', 'Coupon Number'),
        RecordSpec('origin_city', 21, 3, 'A', 'Origin City Code'),
        RecordSpec('filler', 24, 113, 'A', 'Filler'),
    ],

    # BKI63 - Itinerary Segment
    'BKI63': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('coupon_number', 18, 3, 'N', 'Coupon Number'),
        RecordSpec('origin', 21, 3, 'A', 'Origin Airport'),
        RecordSpec('destination', 24, 3, 'A', 'Destination Airport'),
        RecordSpec('carrier', 27, 3, 'AN', 'Operating Carrier Code'),
        RecordSpec('class_of_service', 30, 1, 'A', 'Class of Service'),
        RecordSpec('flight_date', 32, 6, 'N', 'Flight Date YYMMDD'),
        RecordSpec('flight_date_2', 38, 6, 'N', 'Arrival Date YYMMDD'),
        RecordSpec('stopover', 44, 4, 'A', 'Stopover Code'),
        RecordSpec('departure_time', 48, 4, 'N', 'Departure Time HHMM'),
        RecordSpec('arrival_time', 52, 4, 'N', 'Arrival Time HHMM'),
        RecordSpec('flight_number', 56, 5, 'AN', 'Flight Number'),
        RecordSpec('filler', 61, 76, 'A', 'Filler'),
    ],

    # BAR64 - Passenger Name
    'BAR64': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('passenger_name', 18, 49, 'A', 'Passenger Name (SURNAME/FIRSTNAME)'),
        RecordSpec('passenger_type', 67, 3, 'A', 'Passenger Type (ADT/CHD/INF)'),
        RecordSpec('filler', 70, 67, 'A', 'Filler'),
    ],

    # BAR66 - Form of Payment Detail
    'BAR66': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('fop_type', 18, 2, 'A', 'Form of Payment Type'),
        RecordSpec('card_type', 20, 4, 'A', 'Card Type (VISA, etc.)'),
        RecordSpec('card_number', 24, 20, 'AN', 'Card Number (masked)'),
        RecordSpec('expiry_date', 44, 4, 'N', 'Expiry Date MMYY'),
        RecordSpec('filler', 48, 89, 'A', 'Filler'),
    ],

    # BKP84 - Payment Information
    'BKP84': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_number', 12, 6, 'N', 'Transaction Number'),
        RecordSpec('fop_type', 18, 4, 'A', 'Form of Payment Type'),
        RecordSpec('fop_amount', 22, 12, 'N', 'FOP Amount (with sign)'),
        RecordSpec('currency', 34, 3, 'A', 'Currency Code'),
        RecordSpec('card_number', 37, 20, 'AN', 'Card Number'),
        RecordSpec('expiry', 57, 4, 'N', 'Expiry MMYY'),
        RecordSpec('filler', 61, 76, 'A', 'Filler'),
    ],

    # BOT93 - Transaction Totals
    'BOT93': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('transaction_code', 12, 4, 'A', 'Transaction Code'),
        RecordSpec('currency', 16, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 19, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 25, 12, 'N', 'Total Fare (with sign)'),
        RecordSpec('tax_total', 37, 11, 'N', 'Total Tax'),
        RecordSpec('penalty_total', 48, 11, 'N', 'Total Penalty'),
        RecordSpec('net_remit_total', 59, 12, 'N', 'Net Remittance (with sign)'),
        RecordSpec('total_amount', 71, 12, 'N', 'Total Amount (with sign)'),
        RecordSpec('filler', 83, 54, 'A', 'Filler'),
    ],

    # BOT94 - Office Totals
    'BOT94': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('currency', 12, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 15, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 21, 12, 'N', 'Total Fare (with sign)'),
        RecordSpec('tax_total', 33, 11, 'N', 'Total Tax'),
        RecordSpec('penalty_total', 44, 11, 'N', 'Total Penalty'),
        RecordSpec('net_remit_total', 55, 12, 'N', 'Net Remittance (with sign)'),
        RecordSpec('total_amount', 67, 12, 'N', 'Total Amount (with sign)'),
        RecordSpec('filler', 79, 58, 'A', 'Filler'),
    ],

    # BCT95 - Billing Analysis Totals
    'BCT95': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('currency', 12, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 15, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 21, 12, 'N', 'Total Fare (with sign)'),
        RecordSpec('tax_total', 33, 11, 'N', 'Total Tax'),
        RecordSpec('penalty_total', 44, 11, 'N', 'Total Penalty'),
        RecordSpec('net_remit_total', 55, 12, 'N', 'Net Remittance (with sign)'),
        RecordSpec('total_amount', 67, 12, 'N', 'Total Amount (with sign)'),
        RecordSpec('filler', 79, 58, 'A', 'Filler'),
    ],

    # BFT99 - File Totals
    'BFT99': [
        RecordSpec('record_id', 1, 5, 'A', 'Record Identifier'),
        RecordSpec('sequence_number', 6, 6, 'N', 'Sequence Number'),
        RecordSpec('currency', 12, 3, 'A', 'Currency Code'),
        RecordSpec('document_count', 15, 6, 'N', 'Document Count'),
        RecordSpec('fare_total', 21, 12, 'N', 'Total Fare (with sign)'),
        RecordSpec('tax_total', 33, 11, 'N', 'Total Tax'),
        RecordSpec('penalty_total', 44, 11, 'N', 'Total Penalty'),
        RecordSpec('net_remit_total', 55, 12, 'N', 'Net Remittance (with sign)'),
        RecordSpec('total_amount', 67, 12, 'N', 'Total Amount (with sign)'),
        RecordSpec('filler', 79, 58, 'A', 'Filler'),
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
    issue_date: Optional[datetime] = None
    passenger_name: str = ""
    passenger_type: str = ""

    # Financial
    currency: str = ""
    fare_amount: Decimal = Decimal('0')
    total_tax: Decimal = Decimal('0')
    penalty: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    commission_amount: Decimal = Decimal('0')
    commission_rate: Decimal = Decimal('0')
    net_remit: Decimal = Decimal('0')

    # Taxes breakdown
    taxes: List[Dict[str, Any]] = field(default_factory=list)

    # Itinerary
    origin_city: str = ""
    segments: List[Dict[str, Any]] = field(default_factory=list)

    # Payment
    fop_type: str = ""
    card_type: str = ""
    card_number: str = ""

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

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def parse_file(self, filepath: str) -> HOTFile:
        """Parse a HOT file and return structured data"""
        with open(filepath, 'r', encoding='latin-1') as f:
            content = f.read()
        return self.parse_content(content)

    def parse_content(self, content: str) -> HOTFile:
        """Parse HOT content string"""
        hot_file = HOTFile()
        lines = content.strip().split('\n')

        current_agent: Optional[Agent] = None
        current_document: Optional[TicketDocument] = None

        for line_num, line in enumerate(lines, 1):
            # Pad line to 136 characters if needed
            if len(line) < self.RECORD_LENGTH:
                line = line.ljust(self.RECORD_LENGTH)

            record_id = line[:5]
            parsed = self._parse_record(line, record_id)

            if parsed is None:
                self.warnings.append(f"Line {line_num}: Unknown record type '{record_id}'")
                continue

            hot_file.raw_records.append(parsed)

            # Process based on record type
            if record_id == 'BFH01':
                self._process_file_header(hot_file, parsed)

            elif record_id == 'BCH02':
                self._process_billing_header(hot_file, parsed)

            elif record_id == 'BOH03':
                # New agent
                if current_agent:
                    hot_file.agents.append(current_agent)
                current_agent = Agent()
                self._process_office_header(current_agent, parsed)

            elif record_id == 'BKT06':
                # New transaction group (can contain multiple documents)
                pass

            elif record_id == 'BKS24':
                # New document
                if current_document and current_agent:
                    current_agent.documents.append(current_document)
                current_document = TicketDocument()
                self._process_document_id(current_document, parsed)

            elif record_id == 'BKS30' and current_document:
                self._process_amounts(current_document, parsed)

            elif record_id == 'BKS31' and current_document:
                self._process_tax(current_document, parsed)

            elif record_id == 'BKS39' and current_document:
                self._process_commission(current_document, parsed)

            elif record_id == 'BKI61' and current_document:
                self._process_origin(current_document, parsed)

            elif record_id == 'BKI63' and current_document:
                self._process_segment(current_document, parsed)

            elif record_id == 'BAR64' and current_document:
                self._process_passenger(current_document, parsed)

            elif record_id in ('BAR66', 'BKP84') and current_document:
                self._process_payment(current_document, parsed)

            elif record_id == 'BOT94' and current_agent:
                self._process_office_totals(current_agent, parsed)

            elif record_id == 'BFT99':
                self._process_file_totals(hot_file, parsed)

        # Add last document and agent
        if current_document and current_agent:
            current_agent.documents.append(current_document)
        if current_agent:
            hot_file.agents.append(current_agent)

        return hot_file

    def _parse_record(self, line: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Parse a single record line based on its specification"""
        if record_id not in RECORD_SPECS:
            return None

        result = {'_record_id': record_id, '_raw': line}

        for spec in RECORD_SPECS[record_id]:
            start = spec.start - 1  # Convert to 0-indexed
            end = start + spec.length
            raw_value = line[start:end]

            # Parse based on data type
            if spec.data_type == 'N':
                result[spec.name] = self._parse_numeric(raw_value, spec.name)
            else:
                result[spec.name] = raw_value.strip()

        return result

    def _parse_numeric(self, value: str, field_name: str) -> Decimal:
        """Parse numeric field handling signs and implicit decimals"""
        value = value.strip()
        if not value:
            return Decimal('0')

        # Handle IATA sign convention (} = negative, { = positive at end)
        is_negative = False
        if value.endswith('}'):
            is_negative = True
            value = value[:-1]
        elif value.endswith('{'):
            value = value[:-1]

        # Remove non-numeric except minus
        value = re.sub(r'[^0-9\-]', '', value)

        if not value or value == '-':
            return Decimal('0')

        try:
            # Amounts typically have 2 implied decimal places
            result = Decimal(value) / 100
            if is_negative:
                result = -result
            return result
        except Exception:
            return Decimal('0')

    def _parse_date(self, value: str) -> Optional[datetime]:
        """Parse date in YYMMDD format"""
        value = value.strip()
        if not value or len(value) != 6:
            return None
        try:
            return datetime.strptime(value, '%y%m%d')
        except ValueError:
            return None

    def _process_file_header(self, hot_file: HOTFile, record: Dict):
        hot_file.bsp_code = record.get('bsp_code', '')
        hot_file.file_date = self._parse_date(str(record.get('file_date', '')).zfill(6))
        hot_file.billing_period = str(record.get('billing_period', ''))
        hot_file.dish_version = record.get('dish_version', '')
        hot_file.file_type = record.get('file_type', '')

    def _process_billing_header(self, hot_file: HOTFile, record: Dict):
        hot_file.airline_code = record.get('airline_code', '')
        hot_file.currency = record.get('currency', '')

    def _process_office_header(self, agent: Agent, record: Dict):
        agent.iata_number = record.get('agent_iata_number', '')
        agent.name = record.get('agent_name', '')
        agent.city = record.get('agent_city', '')

    def _process_document_id(self, doc: TicketDocument, record: Dict):
        doc.document_number = record.get('document_number', '')
        doc.transaction_code = record.get('transaction_code', '')
        doc.issue_date = self._parse_date(str(record.get('issue_date', '')).zfill(6))
        doc.raw_records.append(record)

    def _process_amounts(self, doc: TicketDocument, record: Dict):
        doc.currency = record.get('currency', '')
        doc.fare_amount = record.get('fare_amount', Decimal('0'))
        doc.total_tax = record.get('total_tax', Decimal('0'))
        doc.penalty = record.get('penalty', Decimal('0'))
        doc.total_amount = record.get('total_amount', Decimal('0'))
        doc.raw_records.append(record)

    def _process_tax(self, doc: TicketDocument, record: Dict):
        tax_info = {
            'country': record.get('tax_country', ''),
            'currency': record.get('currency', ''),
            'code': record.get('tax_code', ''),
            'amount': record.get('tax_amount', Decimal('0')),
        }
        doc.taxes.append(tax_info)
        doc.raw_records.append(record)

    def _process_commission(self, doc: TicketDocument, record: Dict):
        doc.commission_amount = record.get('comm_amount', Decimal('0'))
        doc.commission_rate = record.get('comm_rate', Decimal('0')) / 100  # Convert from x100
        doc.net_remit = record.get('net_remit', Decimal('0'))
        doc.raw_records.append(record)

    def _process_origin(self, doc: TicketDocument, record: Dict):
        doc.origin_city = record.get('origin_city', '')
        doc.raw_records.append(record)

    def _process_segment(self, doc: TicketDocument, record: Dict):
        segment = {
            'coupon': record.get('coupon_number', ''),
            'origin': record.get('origin', ''),
            'destination': record.get('destination', ''),
            'carrier': record.get('carrier', ''),
            'class': record.get('class_of_service', ''),
            'flight_date': self._parse_date(str(record.get('flight_date', '')).zfill(6)),
            'departure_time': record.get('departure_time', ''),
            'arrival_time': record.get('arrival_time', ''),
            'flight_number': record.get('flight_number', ''),
        }
        doc.segments.append(segment)
        doc.raw_records.append(record)

    def _process_passenger(self, doc: TicketDocument, record: Dict):
        doc.passenger_name = record.get('passenger_name', '')
        doc.passenger_type = record.get('passenger_type', '')
        doc.raw_records.append(record)

    def _process_payment(self, doc: TicketDocument, record: Dict):
        doc.fop_type = record.get('fop_type', '')
        doc.card_type = record.get('card_type', '')
        doc.card_number = record.get('card_number', '')
        doc.raw_records.append(record)

    def _process_office_totals(self, agent: Agent, record: Dict):
        agent.document_count = int(record.get('document_count', 0))
        agent.total_fare = record.get('fare_total', Decimal('0'))
        agent.total_tax = record.get('tax_total', Decimal('0'))
        agent.total_amount = record.get('total_amount', Decimal('0'))
        agent.net_remit = record.get('net_remit_total', Decimal('0'))

    def _process_file_totals(self, hot_file: HOTFile, record: Dict):
        hot_file.total_documents = int(record.get('document_count', 0))
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
    lines.append(f"File Date:       {hot_file.file_date}")
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
            lines.append(f"    Type: {doc.transaction_code}")
            lines.append(f"    Passenger: {doc.passenger_name} ({doc.passenger_type})")
            lines.append(f"    Issue Date: {doc.issue_date}")
            lines.append(f"    Fare: {doc.currency} {doc.fare_amount:,.2f}")
            lines.append(f"    Tax: {doc.currency} {doc.total_tax:,.2f}")
            lines.append(f"    Total: {doc.currency} {doc.total_amount:,.2f}")
            lines.append(f"    Commission: {doc.commission_rate:.2%} ({doc.currency} {doc.commission_amount:,.2f})")
            lines.append(f"    Net Remit: {doc.currency} {doc.net_remit:,.2f}")
            lines.append(f"    Payment: {doc.fop_type} {doc.card_type} {doc.card_number}")

            # Itinerary
            if doc.segments:
                lines.append(f"    Origin: {doc.origin_city}")
                lines.append("    Itinerary:")
                for seg in doc.segments:
                    lines.append(f"      {seg['coupon']}: {seg['origin']}-{seg['destination']} "
                               f"{seg['carrier']}{seg['flight_number']} {seg['class']} "
                               f"{seg['flight_date']} {seg['departure_time']}-{seg['arrival_time']}")

            # Taxes
            if doc.taxes:
                lines.append("    Taxes:")
                for tax in doc.taxes:
                    lines.append(f"      {tax['code']}: {tax['currency']} {tax['amount']:,.2f} ({tax['country']})")

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
                    f"{s['origin']}-{s['destination']}" for s in doc.segments
                ])

                writer.writerow([
                    agent.iata_number, agent.name, agent.city,
                    doc.document_number, doc.transaction_code,
                    doc.issue_date.strftime('%Y-%m-%d') if doc.issue_date else '',
                    doc.passenger_name, doc.passenger_type,
                    doc.currency, doc.fare_amount, doc.total_tax, doc.total_amount,
                    doc.commission_rate, doc.commission_amount, doc.net_remit,
                    doc.fop_type, doc.card_type,
                    doc.origin_city, itinerary
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
                'issue_date': doc.issue_date,
                'passenger': {
                    'name': doc.passenger_name,
                    'type': doc.passenger_type,
                },
                'amounts': {
                    'currency': doc.currency,
                    'fare': doc.fare_amount,
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
                    'card_type': doc.card_type,
                    'card_number': doc.card_number,
                },
                'itinerary': {
                    'origin': doc.origin_city,
                    'segments': doc.segments,
                },
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

    parser = argparse.ArgumentParser(description='IATA DISH HOT File Parser')
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
        for w in hot_parser.warnings:
            print(f"  - {w}")
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
