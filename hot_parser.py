"""
IATA HOT/LIFT Parser - DISH Revision 23 Specification
Parses BSP (Billing and Settlement Plan) HOT (Hand-Off Transmission) and LIFT files
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from decimal import Decimal, InvalidOperation
from datetime import datetime
import re


# IATA Overpunch sign convention for numeric fields
OVERPUNCH_POSITIVE = {'{': '0', 'A': '1', 'B': '2', 'C': '3', 'D': '4',
                       'E': '5', 'F': '6', 'G': '7', 'H': '8', 'I': '9'}
OVERPUNCH_NEGATIVE = {'}': '0', 'J': '1', 'K': '2', 'L': '3', 'M': '4',
                       'N': '5', 'O': '6', 'P': '7', 'Q': '8', 'R': '9'}


@dataclass
class TaxDetail:
    """Represents a tax breakdown entry"""
    country_code: str = ""
    tax_code: str = ""
    amount: Decimal = Decimal('0')


@dataclass
class ItinerarySegment:
    """Represents a flight segment in the itinerary"""
    origin: str = ""
    destination: str = ""
    carrier: str = ""
    flight_number: str = ""
    flight_date: str = ""
    booking_class: str = ""
    fare_basis: str = ""
    stopover_indicator: str = ""


@dataclass
class TicketDocument:
    """Represents a single ticket/document"""
    document_number: str = ""
    transaction_code: str = ""  # TKTT, RFND, EXCH, etc.
    issue_date: str = ""

    # Passenger info
    passenger_name: str = ""
    passenger_type: str = ""  # ADT, CHD, INF

    # Financial data
    fare_amount: Decimal = Decimal('0')
    tax_amount: Decimal = Decimal('0')
    penalty_amount: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    commission_rate: Decimal = Decimal('0')
    commission_amount: Decimal = Decimal('0')
    net_remittance: Decimal = Decimal('0')

    # Itinerary
    origin_city: str = ""
    destination_city: str = ""
    itinerary: List[ItinerarySegment] = field(default_factory=list)

    # Tax breakdown
    taxes: List[TaxDetail] = field(default_factory=list)

    # Payment info
    fop_type: str = ""  # CA, CC, MS, etc.
    card_type: str = ""
    card_number: str = ""
    approval_code: str = ""

    # Conjunction tickets
    conjunction_ticket: str = ""

    # Original document for refunds/exchanges
    original_document_number: str = ""
    original_issue_date: str = ""


@dataclass
class Agent:
    """Represents a travel agent/office"""
    iata_number: str = ""
    name: str = ""
    city: str = ""
    country: str = ""

    # Documents processed by this agent
    documents: List[TicketDocument] = field(default_factory=list)

    # Agent totals
    total_fare: Decimal = Decimal('0')
    total_tax: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    total_net_remit: Decimal = Decimal('0')
    document_count: int = 0


@dataclass
class HOTFile:
    """Represents the complete parsed HOT/LIFT file"""
    # File metadata
    bsp_code: str = ""
    file_date: str = ""
    billing_period: str = ""
    airline_code: str = ""
    airline_name: str = ""
    currency_code: str = ""
    dish_version: str = ""
    file_type: str = ""  # HOT or LIFT

    # Agents with their documents
    agents: List[Agent] = field(default_factory=list)

    # File totals
    total_documents: int = 0
    total_fare: Decimal = Decimal('0')
    total_tax: Decimal = Decimal('0')
    total_amount: Decimal = Decimal('0')
    total_net_remit: Decimal = Decimal('0')

    # Parsing info
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw_records: List[str] = field(default_factory=list)


class HOTParser:
    """Parser for IATA HOT/LIFT files following DISH Revision 23 specification"""

    RECORD_LENGTH = 136

    # Record type definitions with field positions (1-indexed as per spec)
    RECORD_TYPES = {
        'BFH': 'File Header',
        'BCH': 'Billing Analysis Header',
        'BOH': 'Office Header',
        'BKT': 'Transaction Header',
        'BKS': 'Transaction Segment',
        'BKI': 'Itinerary Segment',
        'BAR': 'Additional Record',
        'BKP': 'Payment Record',
        'BOT': 'Office Totals',
        'BCT': 'Billing Analysis Totals',
        'BFT': 'File Totals'
    }

    def __init__(self):
        self.hot_file = HOTFile()
        self.current_agent: Optional[Agent] = None
        self.current_document: Optional[TicketDocument] = None
        self.line_number = 0

    def parse(self, content: str) -> HOTFile:
        """Parse HOT/LIFT file content and return structured data"""
        self.hot_file = HOTFile()
        self.current_agent = None
        self.current_document = None
        self.line_number = 0

        # Handle files with or without line breaks
        if '\n' in content or '\r' in content:
            lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        else:
            # Fixed-width file without line breaks
            lines = [content[i:i+self.RECORD_LENGTH]
                    for i in range(0, len(content), self.RECORD_LENGTH)]

        for line in lines:
            self.line_number += 1
            line = line.rstrip('\n\r')

            if not line or len(line) < 5:
                continue

            self.hot_file.raw_records.append(line)
            self._parse_record(line)

        # Finalize any pending document/agent
        self._finalize_document()
        self._finalize_agent()

        # Calculate file totals from agents
        self._calculate_totals()

        return self.hot_file

    def _parse_record(self, line: str) -> None:
        """Parse a single record based on its type"""
        # Get record identifier (positions 1-5)
        record_id = line[0:5] if len(line) >= 5 else ""
        record_prefix = record_id[0:3] if len(record_id) >= 3 else ""

        try:
            if record_prefix == 'BFH':
                self._parse_file_header(line)
            elif record_prefix == 'BCH':
                self._parse_billing_header(line)
            elif record_prefix == 'BOH':
                self._parse_office_header(line)
            elif record_prefix == 'BKT':
                self._parse_transaction_header(line)
            elif record_prefix == 'BKS':
                self._parse_transaction_segment(line)
            elif record_prefix == 'BKI':
                self._parse_itinerary_segment(line)
            elif record_prefix == 'BAR':
                self._parse_additional_record(line)
            elif record_prefix == 'BKP':
                self._parse_payment_record(line)
            elif record_prefix == 'BOT':
                self._parse_office_totals(line)
            elif record_prefix == 'BCT':
                self._parse_billing_totals(line)
            elif record_prefix == 'BFT':
                self._parse_file_totals(line)
            else:
                self.hot_file.warnings.append(
                    f"Line {self.line_number}: Unknown record type '{record_id}'"
                )
        except Exception as e:
            self.hot_file.errors.append(
                f"Line {self.line_number}: Error parsing record - {str(e)}"
            )

    def _parse_file_header(self, line: str) -> None:
        """Parse BFH01 - File Header record"""
        # Positions based on DISH spec
        self.hot_file.bsp_code = self._get_field(line, 6, 3).strip()
        self.hot_file.file_date = self._parse_date(self._get_field(line, 9, 6))
        self.hot_file.billing_period = self._get_field(line, 15, 6).strip()
        self.hot_file.dish_version = self._get_field(line, 21, 2).strip()

        # Determine file type from record content or extension
        file_type_indicator = self._get_field(line, 23, 1).strip()
        if file_type_indicator == 'H':
            self.hot_file.file_type = 'HOT'
        elif file_type_indicator == 'L':
            self.hot_file.file_type = 'LIFT'
        else:
            self.hot_file.file_type = 'HOT'  # Default

    def _parse_billing_header(self, line: str) -> None:
        """Parse BCH02 - Billing Analysis Header record"""
        self.hot_file.airline_code = self._get_field(line, 6, 3).strip()
        self.hot_file.currency_code = self._get_field(line, 9, 3).strip()

        # Billing type indicator
        billing_type = self._get_field(line, 12, 2).strip()
        if billing_type:
            self.hot_file.file_type = 'HOT' if billing_type in ('01', '02') else 'LIFT'

    def _parse_office_header(self, line: str) -> None:
        """Parse BOH03 - Office Header record (Agent info)"""
        # Finalize previous agent if any
        self._finalize_document()
        self._finalize_agent()

        self.current_agent = Agent()
        self.current_agent.iata_number = self._get_field(line, 6, 8).strip()
        self.current_agent.name = self._get_field(line, 14, 52).strip()
        self.current_agent.city = self._get_field(line, 66, 25).strip()
        self.current_agent.country = self._get_field(line, 91, 2).strip()

    def _parse_transaction_header(self, line: str) -> None:
        """Parse BKT06 - Transaction Header record"""
        # Finalize previous document if any
        self._finalize_document()

        self.current_document = TicketDocument()

        # Transaction code
        trans_code = self._get_field(line, 6, 4).strip()
        self.current_document.transaction_code = self._map_transaction_code(trans_code)

    def _parse_transaction_segment(self, line: str) -> None:
        """Parse BKS records - various transaction segments"""
        if not self.current_document:
            self.current_document = TicketDocument()

        record_id = line[0:5] if len(line) >= 5 else ""
        segment_type = record_id[3:5] if len(record_id) >= 5 else ""

        # BKS24 - Document identification
        if segment_type in ('24', '00'):
            self._parse_document_id(line)
        # BKS30 - Document amounts
        elif segment_type == '30':
            self._parse_document_amounts(line)
        # BKS31 - Tax breakdown
        elif segment_type == '31':
            self._parse_tax_breakdown(line)
        # BKS39 - Commission
        elif segment_type == '39':
            self._parse_commission(line)
        else:
            # Try to auto-detect segment type based on content
            self._parse_generic_bks(line)

    def _parse_document_id(self, line: str) -> None:
        """Parse BKS24 - Document identification"""
        if not self.current_document:
            return

        self.current_document.document_number = self._get_field(line, 6, 13).strip()

        # Transaction code if not already set
        trans_code = self._get_field(line, 19, 4).strip()
        if trans_code and not self.current_document.transaction_code:
            self.current_document.transaction_code = self._map_transaction_code(trans_code)

        # Issue date
        issue_date = self._get_field(line, 23, 6).strip()
        if issue_date:
            self.current_document.issue_date = self._parse_date(issue_date)

        # Conjunction ticket
        self.current_document.conjunction_ticket = self._get_field(line, 29, 13).strip()

        # Original document for refunds
        self.current_document.original_document_number = self._get_field(line, 42, 13).strip()
        orig_date = self._get_field(line, 55, 6).strip()
        if orig_date:
            self.current_document.original_issue_date = self._parse_date(orig_date)

    def _parse_document_amounts(self, line: str) -> None:
        """Parse BKS30 - Document amounts"""
        if not self.current_document:
            return

        self.current_document.fare_amount = self._parse_amount(self._get_field(line, 6, 12))
        self.current_document.tax_amount = self._parse_amount(self._get_field(line, 18, 12))
        self.current_document.penalty_amount = self._parse_amount(self._get_field(line, 30, 12))
        self.current_document.total_amount = self._parse_amount(self._get_field(line, 42, 12))

    def _parse_tax_breakdown(self, line: str) -> None:
        """Parse BKS31 - Tax breakdown"""
        if not self.current_document:
            return

        # Multiple taxes can be in one record
        pos = 6
        while pos + 14 <= len(line):
            country = self._get_field(line, pos, 2).strip()
            tax_code = self._get_field(line, pos + 2, 2).strip()
            amount = self._parse_amount(self._get_field(line, pos + 4, 10))

            if country or tax_code or amount != Decimal('0'):
                tax = TaxDetail(
                    country_code=country,
                    tax_code=tax_code,
                    amount=amount
                )
                self.current_document.taxes.append(tax)

            pos += 14

    def _parse_commission(self, line: str) -> None:
        """Parse BKS39 - Commission information"""
        if not self.current_document:
            return

        self.current_document.commission_rate = self._parse_amount(self._get_field(line, 6, 5), decimals=2)
        self.current_document.commission_amount = self._parse_amount(self._get_field(line, 11, 12))
        self.current_document.net_remittance = self._parse_amount(self._get_field(line, 23, 12))

    def _parse_generic_bks(self, line: str) -> None:
        """Generic BKS parser for unrecognized segment types"""
        if not self.current_document:
            return

        # Try to extract document number if present
        potential_doc = self._get_field(line, 6, 13).strip()
        if potential_doc and potential_doc.isdigit() and len(potential_doc) >= 10:
            if not self.current_document.document_number:
                self.current_document.document_number = potential_doc

    def _parse_itinerary_segment(self, line: str) -> None:
        """Parse BKI records - Itinerary segments"""
        if not self.current_document:
            return

        record_id = line[0:5] if len(line) >= 5 else ""
        segment_type = record_id[3:5] if len(record_id) >= 5 else ""

        # BKI61 - Origin city
        if segment_type == '61':
            self.current_document.origin_city = self._get_field(line, 6, 3).strip()
            self.current_document.destination_city = self._get_field(line, 9, 3).strip()
        # BKI63 - Flight segment
        elif segment_type == '63':
            segment = ItinerarySegment()
            segment.origin = self._get_field(line, 6, 3).strip()
            segment.destination = self._get_field(line, 9, 3).strip()
            segment.carrier = self._get_field(line, 12, 2).strip()
            segment.flight_number = self._get_field(line, 14, 4).strip()
            segment.booking_class = self._get_field(line, 18, 1).strip()
            segment.flight_date = self._parse_date(self._get_field(line, 19, 6))
            segment.fare_basis = self._get_field(line, 25, 13).strip()
            segment.stopover_indicator = self._get_field(line, 38, 1).strip()

            if segment.origin or segment.destination:
                self.current_document.itinerary.append(segment)
        else:
            # Try generic itinerary parsing
            segment = ItinerarySegment()
            segment.origin = self._get_field(line, 6, 3).strip()
            segment.destination = self._get_field(line, 9, 3).strip()
            if segment.origin and segment.destination:
                self.current_document.itinerary.append(segment)

    def _parse_additional_record(self, line: str) -> None:
        """Parse BAR records - Additional records (passenger, payment, etc.)"""
        if not self.current_document:
            return

        record_id = line[0:5] if len(line) >= 5 else ""
        segment_type = record_id[3:5] if len(record_id) >= 5 else ""

        # BAR64 - Passenger information
        if segment_type == '64':
            self.current_document.passenger_name = self._get_field(line, 6, 49).strip()
            self.current_document.passenger_type = self._get_field(line, 55, 3).strip()
        # BAR66 - Payment information
        elif segment_type == '66':
            self._parse_payment_info(line)
        else:
            # Try to extract passenger name from any BAR record
            potential_name = self._get_field(line, 6, 49).strip()
            if potential_name and '/' in potential_name:
                self.current_document.passenger_name = potential_name

    def _parse_payment_record(self, line: str) -> None:
        """Parse BKP84 - Payment record"""
        self._parse_payment_info(line)

    def _parse_payment_info(self, line: str) -> None:
        """Parse payment information from BAR66 or BKP84"""
        if not self.current_document:
            return

        self.current_document.fop_type = self._get_field(line, 6, 2).strip()
        self.current_document.card_type = self._get_field(line, 8, 2).strip()

        # Card number (may be masked)
        card_num = self._get_field(line, 10, 19).strip()
        if card_num:
            self.current_document.card_number = card_num

        self.current_document.approval_code = self._get_field(line, 29, 6).strip()

    def _parse_office_totals(self, line: str) -> None:
        """Parse BOT94 - Office totals"""
        if self.current_agent:
            self.current_agent.total_fare = self._parse_amount(self._get_field(line, 6, 15))
            self.current_agent.total_tax = self._parse_amount(self._get_field(line, 21, 15))
            self.current_agent.total_amount = self._parse_amount(self._get_field(line, 36, 15))
            self.current_agent.total_net_remit = self._parse_amount(self._get_field(line, 51, 15))

            doc_count = self._get_field(line, 66, 6).strip()
            if doc_count and doc_count.isdigit():
                self.current_agent.document_count = int(doc_count)

    def _parse_billing_totals(self, line: str) -> None:
        """Parse BCT95 - Billing analysis totals"""
        pass  # Intermediate totals, not usually needed

    def _parse_file_totals(self, line: str) -> None:
        """Parse BFT99 - File totals"""
        self.hot_file.total_fare = self._parse_amount(self._get_field(line, 6, 15))
        self.hot_file.total_tax = self._parse_amount(self._get_field(line, 21, 15))
        self.hot_file.total_amount = self._parse_amount(self._get_field(line, 36, 15))
        self.hot_file.total_net_remit = self._parse_amount(self._get_field(line, 51, 15))

        doc_count = self._get_field(line, 66, 8).strip()
        if doc_count and doc_count.isdigit():
            self.hot_file.total_documents = int(doc_count)

    def _finalize_document(self) -> None:
        """Finalize current document and add to current agent"""
        if self.current_document and self.current_agent:
            if self.current_document.document_number:
                self.current_agent.documents.append(self.current_document)
        self.current_document = None

    def _finalize_agent(self) -> None:
        """Finalize current agent and add to file"""
        if self.current_agent:
            if self.current_agent.iata_number or self.current_agent.documents:
                # Calculate agent totals from documents if not set
                if not self.current_agent.total_amount and self.current_agent.documents:
                    for doc in self.current_agent.documents:
                        self.current_agent.total_fare += doc.fare_amount
                        self.current_agent.total_tax += doc.tax_amount
                        self.current_agent.total_amount += doc.total_amount
                        self.current_agent.total_net_remit += doc.net_remittance
                    self.current_agent.document_count = len(self.current_agent.documents)

                self.hot_file.agents.append(self.current_agent)
        self.current_agent = None

    def _calculate_totals(self) -> None:
        """Calculate file totals from agents if not set from BFT record"""
        if not self.hot_file.total_amount and self.hot_file.agents:
            for agent in self.hot_file.agents:
                self.hot_file.total_fare += agent.total_fare
                self.hot_file.total_tax += agent.total_tax
                self.hot_file.total_amount += agent.total_amount
                self.hot_file.total_net_remit += agent.total_net_remit
                self.hot_file.total_documents += agent.document_count or len(agent.documents)

    def _get_field(self, line: str, start: int, length: int) -> str:
        """Extract field from line (1-indexed positions as per spec)"""
        # Convert to 0-indexed
        start_idx = start - 1
        end_idx = start_idx + length
        if len(line) >= end_idx:
            return line[start_idx:end_idx]
        elif len(line) > start_idx:
            return line[start_idx:]
        return ""

    def _parse_amount(self, value: str, decimals: int = 2) -> Decimal:
        """Parse IATA numeric amount with overpunch sign convention"""
        if not value or not value.strip():
            return Decimal('0')

        value = value.strip()
        if not value:
            return Decimal('0')

        # Check for overpunch in last character
        last_char = value[-1]
        is_negative = False

        if last_char in OVERPUNCH_POSITIVE:
            value = value[:-1] + OVERPUNCH_POSITIVE[last_char]
        elif last_char in OVERPUNCH_NEGATIVE:
            value = value[:-1] + OVERPUNCH_NEGATIVE[last_char]
            is_negative = True

        # Remove non-numeric characters except minus sign
        cleaned = re.sub(r'[^0-9\-]', '', value)
        if not cleaned:
            return Decimal('0')

        try:
            amount = Decimal(cleaned)
            # Apply implicit decimal places
            amount = amount / (10 ** decimals)
            if is_negative:
                amount = -amount
            return amount
        except InvalidOperation:
            return Decimal('0')

    def _parse_date(self, value: str) -> str:
        """Parse date in YYMMDD or DDMMYY format"""
        if not value or len(value) < 6:
            return ""

        value = value.strip()
        if not value or not value.isdigit():
            return ""

        try:
            # Try YYMMDD format first (most common in IATA)
            year = int(value[0:2])
            month = int(value[2:4])
            day = int(value[4:6])

            # Validate
            if 1 <= month <= 12 and 1 <= day <= 31:
                year_full = 2000 + year if year < 50 else 1900 + year
                return f"{year_full:04d}-{month:02d}-{day:02d}"

            # Try DDMMYY format
            day = int(value[0:2])
            month = int(value[2:4])
            year = int(value[4:6])

            if 1 <= month <= 12 and 1 <= day <= 31:
                year_full = 2000 + year if year < 50 else 1900 + year
                return f"{year_full:04d}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            pass

        return value  # Return original if parsing fails

    def _map_transaction_code(self, code: str) -> str:
        """Map transaction code to readable type"""
        code_map = {
            'TKTT': 'TKTT',  # Ticket
            'RFND': 'RFND',  # Refund
            'EXCH': 'EXCH',  # Exchange
            'CANN': 'CANN',  # Cancellation
            'ADMA': 'ADMA',  # ADM Agent
            'ACMA': 'ACMA',  # ACM Agent
            'TKTA': 'TKTA',  # Ticket Agent
            'EMDA': 'EMDA',  # EMD Agent
            'EMDS': 'EMDS',  # EMD
            'BPAS': 'BPAS',  # Boarding Pass
        }
        return code_map.get(code.upper(), code.upper() if code else 'TKTT')


def parse_hot_file(content: str) -> HOTFile:
    """Convenience function to parse HOT/LIFT file content"""
    parser = HOTParser()
    return parser.parse(content)


def hot_file_to_dict(hot_file: HOTFile) -> Dict[str, Any]:
    """Convert HOTFile to dictionary for JSON serialization"""
    return {
        'bsp_code': hot_file.bsp_code,
        'file_date': hot_file.file_date,
        'billing_period': hot_file.billing_period,
        'airline_code': hot_file.airline_code,
        'airline_name': hot_file.airline_name,
        'currency_code': hot_file.currency_code,
        'dish_version': hot_file.dish_version,
        'file_type': hot_file.file_type,
        'totals': {
            'documents': hot_file.total_documents,
            'fare': str(hot_file.total_fare),
            'tax': str(hot_file.total_tax),
            'amount': str(hot_file.total_amount),
            'net_remit': str(hot_file.total_net_remit)
        },
        'agents': [
            {
                'iata_number': agent.iata_number,
                'name': agent.name,
                'city': agent.city,
                'country': agent.country,
                'totals': {
                    'documents': agent.document_count or len(agent.documents),
                    'fare': str(agent.total_fare),
                    'tax': str(agent.total_tax),
                    'amount': str(agent.total_amount),
                    'net_remit': str(agent.total_net_remit)
                },
                'documents': [
                    {
                        'document_number': doc.document_number,
                        'transaction_code': doc.transaction_code,
                        'issue_date': doc.issue_date,
                        'passenger_name': doc.passenger_name,
                        'passenger_type': doc.passenger_type,
                        'fare': str(doc.fare_amount),
                        'tax': str(doc.tax_amount),
                        'penalty': str(doc.penalty_amount),
                        'total': str(doc.total_amount),
                        'commission_rate': str(doc.commission_rate),
                        'commission': str(doc.commission_amount),
                        'net_remittance': str(doc.net_remittance),
                        'origin': doc.origin_city,
                        'destination': doc.destination_city,
                        'itinerary': [
                            {
                                'origin': seg.origin,
                                'destination': seg.destination,
                                'carrier': seg.carrier,
                                'flight_number': seg.flight_number,
                                'flight_date': seg.flight_date,
                                'booking_class': seg.booking_class,
                                'fare_basis': seg.fare_basis
                            } for seg in doc.itinerary
                        ],
                        'taxes': [
                            {
                                'country': tax.country_code,
                                'code': tax.tax_code,
                                'amount': str(tax.amount)
                            } for tax in doc.taxes
                        ],
                        'payment': {
                            'fop_type': doc.fop_type,
                            'card_type': doc.card_type,
                            'card_number': doc.card_number,
                            'approval_code': doc.approval_code
                        },
                        'conjunction_ticket': doc.conjunction_ticket,
                        'original_document': doc.original_document_number,
                        'original_issue_date': doc.original_issue_date
                    } for doc in agent.documents
                ]
            } for agent in hot_file.agents
        ],
        'warnings': hot_file.warnings,
        'errors': hot_file.errors
    }
