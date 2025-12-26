#!/usr/bin/env python3
"""
Threat hunting tool that extracts IoCs from MISP and searches them in SIEM
"""

import os
import csv
import json
import logging
import re
from pathlib import Path

import requests
import urllib3
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass
from functools import reduce
from pymisp import PyMISP
from abc import ABC, abstractmethod

urllib3.disable_warnings()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class IoC:
    """Represents an Indicator of Compromise"""
    type: str
    value: str
    event_id: str


@dataclass
class SearchQuery:
    """Represents a SIEM search query"""
    from_date: datetime
    to_date: datetime
    value: str
    query: str
    count: int


class SIEMConnector(ABC):
    """Abstract base class for SIEM connectors"""

    @abstractmethod
    def login(self, host: str, username: str, password: str) -> bool:
        """Login to SIEM system"""
        pass

    @abstractmethod
    def execute_search(self, query: str, from_date: datetime, to_date: datetime) -> int:
        """Execute search query in SIEM"""
        pass


class GenericSIEMConnector(SIEMConnector):
    """Generic SIEM connector with empty implementations"""

    def login(self, host: str, username: str, password: str) -> bool:
        """Generic login implementation - to be overridden"""
        logger.info(f"Login to SIEM at {host}")
        # TODO: Implement actual SIEM login logic
        return True

    def execute_search(self, query: str, from_date: datetime, to_date: datetime) -> int:
        """Generic search implementation - to be overridden"""
        logger.info(f"Executing query: {query} from {from_date} to {to_date}")
        # TODO: Implement actual SIEM search logic
        return 0


def extract_iocs(events: List[Dict[str, Any]], ioc_types: List[str]) -> List[IoC]:
    """Extract IoCs of specified types from MISP events"""

    def extract_from_event(event: Dict[str, Any]) -> List[IoC]:
        if 'Event' not in event:
            return []

        event_data = event['Event']
        event_id = event_data.get('id', '')

        if 'Attribute' not in event_data:
            return []

        return [
            IoC(type=attr['type'], value=attr['value'], event_id=event_id)
            for attr in event_data['Attribute']
            if attr.get('type') in ioc_types
        ]

    # Use reduce to flatten list of lists
    all_iocs = reduce(lambda acc, event: acc + extract_from_event(event), events, [])
    return all_iocs


def build_search_query(ioc: IoC) -> str:
    """Build SIEM search query from IoC"""
    # Generic query builder - customize based on SIEM type
    if ioc.type == 'ip-dst':
        return f'dest_ip="{ioc.value}"'
    elif ioc.type == 'hostname':
        return f'hostname="{ioc.value}" OR dns_query="{ioc.value}"'
    elif ioc.type == 'sha256':
        return f'file_hash="{ioc.value}"'
    return f'value="{ioc.value}"'


def create_search_queries(iocs: List[IoC], search_days: int) -> List[SearchQuery]:
    to_date = datetime.now()
    from_date = to_date - timedelta(days=search_days)

    return [
        SearchQuery(
            from_date=from_date,
            to_date=to_date,
            value=ioc.value,
            query=build_search_query(ioc),
            count=0
        )
        for ioc in iocs
    ]


def execute_siem_searches(siem: SIEMConnector, queries: List[SearchQuery]) -> List[SearchQuery]:
    def execute_single_search(query: SearchQuery) -> SearchQuery:
        query.count = siem.execute_search(query.query, query.from_date, query.to_date)
        return query

    return list(map(execute_single_search, queries))


def save_query_history(queries: List[SearchQuery], filename: str) -> None:
    """Save search query history to CSV"""
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['From', 'To', 'Count', 'Value', 'Query'])
        for query in queries:
            writer.writerow([
                query.from_date.strftime('%Y-%m-%d'),
                query.to_date.strftime('%Y-%m-%d'),
                query.count,
                query.value,
                query.query
            ])


def main(misp_url: str, misp_key: str, misp_days: int, search_days: int,
         siem_host: str, siem_user: str, siem_pass: str) -> List[SearchQuery]:

    # 1. Connect to MISP
    misp = PyMISP(misp_url, misp_key, False)

    # 2. Search MISP events
    date_from = datetime.now() - timedelta(days=misp_days)
    events = misp.search('events', date_from=date_from.strftime('%Y-%m-%d'))

    # 3. Extract IoCs
    ioc_types = ['ip-dst', 'hostname', 'sha256']
    iocs = extract_iocs(events, ioc_types)

    # 4. Extract EventReport
    for event in events:
        if 'EventReport' in event['Event'] and len(event['Event']['EventReport']) > 1:
            title = ""
            match = re.search(r'\[([^\]]+)\]', event['Event']['info'])
            if match:
                title = match.group(1)
            markdown = event['Event']['EventReport'][1]['content']
            output = Path("/shared").joinpath(Path(f"report_{event['Event']['date']}_{event['Event']['id']}_{title}.md"))
            output.write_text(markdown, encoding='utf-8')

    # 5. Create and execute SIEM searches
    siem = GenericSIEMConnector()
    siem.login(siem_host, siem_user, siem_pass)

    # 6. Execute searches and save results
    queries = create_search_queries(iocs, search_days)
    execute_siem_searches(siem, queries)

    query_history_file = "ibh_query_" + datetime.now().strftime('%Y%m%d') + ".csv"
    save_query_history(queries, query_history_file)
    logger.info(f"Processed {len(iocs)} IoCs, executed {len(queries)} queries")

    return queries


if __name__ == "__main__":
    misp_key = os.getenv('MISP_KEY', '')
    if not misp_key and Path("/shared/authkey.txt").exists():
        misp_key = Path("/shared/authkey.txt").read_text().strip()
    else:
        logger.error("MISP_KEY environment variable or /shared/authkey file must be set")
        exit(1)
    main(
        misp_url=os.getenv('MISP_URL', 'https://localhost'),
        misp_key=misp_key,
        misp_days=int(os.getenv('MISP_EVENT_DAYS_BACK', 3)),
        search_days=int(os.getenv('SIEM_SEARCH_TERM', 90)),
        siem_host=os.getenv('SIEM_HOST', 'siem.example.com'),
        siem_user=os.getenv('SIEM_USER', 'admin'),
        siem_pass=os.getenv('SIEM_PASS', 'password')
    )