"""
Raw → Evidence Transformer for PRODUCT_DEFINED and CONFIGURATION_REQUESTED
Local testing implementation (no database writes)
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class EvidenceRow:
    """Represents a single Evidence row to be inserted"""
    raw_event_id: str
    mapping_id: str
    evidence_type: str
    subject_type: str
    subject_id: str
    property_name: str
    asserted_value: Optional[str]
    value_type: str
    source_system: str
    source_actor_id: Optional[str]
    source_actor_role: str
    occurred_at: datetime
    recorded_at: datetime
    arrival_at: datetime
    simulator_classification: Optional[str]
    evidence_lineage: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for inspection"""
        return {
            'raw_event_id': self.raw_event_id,
            'mapping_id': self.mapping_id,
            'evidence_type': self.evidence_type,
            'subject_type': self.subject_type,
            'subject_id': self.subject_id,
            'property_name': self.property_name,
            'asserted_value': self.asserted_value,
            'value_type': self.value_type,
            'source_system': self.source_system,
            'source_actor_id': self.source_actor_id,
            'source_actor_role': self.source_actor_role,
            'occurred_at': self.occurred_at.isoformat(),
            'recorded_at': self.recorded_at.isoformat(),
            'arrival_at': self.arrival_at.isoformat(),
            'simulator_classification': self.simulator_classification,
            'evidence_lineage': self.evidence_lineage,
        }


class RawToEvidenceTransformer:
    """
    Transforms Raw events to Evidence using approved mappings
    Implements STEP 5E.1 design specifications
    """

    def __init__(self):
        self.evidence_rows: List[EvidenceRow] = []
        self.processed_raw_ids: set = set()

    def transform_raw_event(self, raw_event_id: str, raw_payload: Dict[str, Any]) -> List[EvidenceRow]:
        """
        Transform a single Raw event to Evidence rows
        Returns list of Evidence rows (may be empty if no mapping applies)
        """
        rows = []
        event_type = raw_payload.get('event_type')

        if event_type == 'PRODUCT_DEFINED':
            rows.extend(self._transform_product_defined(raw_event_id, raw_payload))
        elif event_type == 'CONFIGURATION_REQUESTED':
            rows.extend(self._transform_configuration_requested(raw_event_id, raw_payload))

        self.evidence_rows.extend(rows)
        self.processed_raw_ids.add(raw_event_id)
        return rows

    def _get_timestamps(self, raw_payload: Dict[str, Any]):
        """Extract timestamps from raw payload"""
        # Parse ISO 8601 timestamps
        occurred_at_str = raw_payload.get('occurred_at', datetime.now(timezone.utc).isoformat())
        recorded_at_str = raw_payload.get('recorded_at', datetime.now(timezone.utc).isoformat())
        arrival_at_str = raw_payload.get('arrival_at', datetime.now(timezone.utc).isoformat())

        # Simple ISO parsing
        try:
            occurred_at = datetime.fromisoformat(occurred_at_str.replace('Z', '+00:00'))
        except:
            occurred_at = datetime.now(timezone.utc)

        try:
            recorded_at = datetime.fromisoformat(recorded_at_str.replace('Z', '+00:00'))
        except:
            recorded_at = datetime.now(timezone.utc)

        try:
            arrival_at = datetime.fromisoformat(arrival_at_str.replace('Z', '+00:00'))
        except:
            arrival_at = datetime.now(timezone.utc)

        return occurred_at, recorded_at, arrival_at

    def _transform_product_defined(self, raw_event_id: str, raw_payload: Dict[str, Any]) -> List[EvidenceRow]:
        """
        PRODUCT_DEFINED → 2 Evidence rows
        Mapping:
        1. product_name (PRODUCT_DEF_NAME)
        2. launch_reference (PRODUCT_DEF_LAUNCH)
        """
        rows = []
        occurred_at, recorded_at, arrival_at = self._get_timestamps(raw_payload)

        source_system = raw_payload.get('source_system', 'product_definition')
        simulator_classification = raw_payload.get('simulator_classification', 'PROTOTYPE_ASSUMPTION')
        product_id = raw_payload.get('product_id')

        # Evidence 1: product_name
        if raw_payload.get('product_name'):
            rows.append(EvidenceRow(
                raw_event_id=raw_event_id,
                mapping_id='PRODUCT_DEF_NAME',
                evidence_type='product_definition',
                subject_type='product',
                subject_id=product_id,
                property_name='product_name',
                asserted_value=raw_payload.get('product_name'),
                value_type='string',
                source_system=source_system,
                source_actor_id=None,
                source_actor_role='process',
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                arrival_at=arrival_at,
                simulator_classification=simulator_classification,
                evidence_lineage={
                    'event_type': 'PRODUCT_DEFINED',
                    'mapping_id': 'PRODUCT_DEF_NAME',
                    'source_path': 'payload.product_name',
                    'raw_event_id': raw_event_id,
                }
            ))

        # Evidence 2: launch_reference
        if raw_payload.get('launch_id'):
            rows.append(EvidenceRow(
                raw_event_id=raw_event_id,
                mapping_id='PRODUCT_DEF_LAUNCH',
                evidence_type='product_definition',
                subject_type='product',
                subject_id=product_id,
                property_name='launch_reference',
                asserted_value=raw_payload.get('launch_id'),
                value_type='string',
                source_system=source_system,
                source_actor_id=None,
                source_actor_role='process',
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                arrival_at=arrival_at,
                simulator_classification=simulator_classification,
                evidence_lineage={
                    'event_type': 'PRODUCT_DEFINED',
                    'mapping_id': 'PRODUCT_DEF_LAUNCH',
                    'source_path': 'payload.launch_id',
                    'raw_event_id': raw_event_id,
                }
            ))

        return rows

    def _transform_configuration_requested(self, raw_event_id: str, raw_payload: Dict[str, Any]) -> List[EvidenceRow]:
        """
        CONFIGURATION_REQUESTED → 5 Evidence rows (or 4 if segment is NULL)
        Mappings:
        1. product_reference (CONF_REQ_PRODUCT)
        2. launch_reference (CONF_REQ_LAUNCH)
        3. geography (CONF_REQ_GEO)
        4. term_months (CONF_REQ_TERM)
        5. customer_segment (CONF_REQ_SEGMENT) — ONLY if not NULL
        """
        rows = []
        occurred_at, recorded_at, arrival_at = self._get_timestamps(raw_payload)

        source_system = raw_payload.get('source_system', 'configuration_governance')
        simulator_classification = raw_payload.get('simulator_classification', 'PROTOTYPE_ASSUMPTION')
        config_request_id = raw_payload.get('configuration_request_id')

        # Evidence 1: product_reference
        if raw_payload.get('product_id'):
            rows.append(EvidenceRow(
                raw_event_id=raw_event_id,
                mapping_id='CONF_REQ_PRODUCT',
                evidence_type='configuration_request',
                subject_type='configuration_request',
                subject_id=config_request_id,
                property_name='product_reference',
                asserted_value=raw_payload.get('product_id'),
                value_type='string',
                source_system=source_system,
                source_actor_id=None,
                source_actor_role='process',
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                arrival_at=arrival_at,
                simulator_classification=simulator_classification,
                evidence_lineage={
                    'event_type': 'CONFIGURATION_REQUESTED',
                    'mapping_id': 'CONF_REQ_PRODUCT',
                    'source_path': 'payload.product_id',
                    'raw_event_id': raw_event_id,
                }
            ))

        # Evidence 2: launch_reference
        if raw_payload.get('launch_id'):
            rows.append(EvidenceRow(
                raw_event_id=raw_event_id,
                mapping_id='CONF_REQ_LAUNCH',
                evidence_type='configuration_request',
                subject_type='configuration_request',
                subject_id=config_request_id,
                property_name='launch_reference',
                asserted_value=raw_payload.get('launch_id'),
                value_type='string',
                source_system=source_system,
                source_actor_id=None,
                source_actor_role='process',
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                arrival_at=arrival_at,
                simulator_classification=simulator_classification,
                evidence_lineage={
                    'event_type': 'CONFIGURATION_REQUESTED',
                    'mapping_id': 'CONF_REQ_LAUNCH',
                    'source_path': 'payload.launch_id',
                    'raw_event_id': raw_event_id,
                }
            ))

        # Evidence 3: geography
        if raw_payload.get('geo'):
            rows.append(EvidenceRow(
                raw_event_id=raw_event_id,
                mapping_id='CONF_REQ_GEO',
                evidence_type='configuration_request',
                subject_type='configuration_request',
                subject_id=config_request_id,
                property_name='geography',
                asserted_value=raw_payload.get('geo'),
                value_type='string',
                source_system=source_system,
                source_actor_id=None,
                source_actor_role='process',
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                arrival_at=arrival_at,
                simulator_classification=simulator_classification,
                evidence_lineage={
                    'event_type': 'CONFIGURATION_REQUESTED',
                    'mapping_id': 'CONF_REQ_GEO',
                    'source_path': 'payload.geo',
                    'raw_event_id': raw_event_id,
                }
            ))

        # Evidence 4: term_months
        term = raw_payload.get('term')
        if term is not None:
            rows.append(EvidenceRow(
                raw_event_id=raw_event_id,
                mapping_id='CONF_REQ_TERM',
                evidence_type='configuration_request',
                subject_type='configuration_request',
                subject_id=config_request_id,
                property_name='term_months',
                asserted_value=str(term),
                value_type='integer',
                source_system=source_system,
                source_actor_id=None,
                source_actor_role='process',
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                arrival_at=arrival_at,
                simulator_classification=simulator_classification,
                evidence_lineage={
                    'event_type': 'CONFIGURATION_REQUESTED',
                    'mapping_id': 'CONF_REQ_TERM',
                    'source_path': 'payload.term',
                    'raw_event_id': raw_event_id,
                }
            ))

        # Evidence 5: customer_segment (ONLY if not NULL)
        # S7 has segment=NULL, so this won't be created for S7
        segment = raw_payload.get('segment')
        if segment is not None:  # Only if segment is NOT NULL
            rows.append(EvidenceRow(
                raw_event_id=raw_event_id,
                mapping_id='CONF_REQ_SEGMENT',
                evidence_type='configuration_request',
                subject_type='configuration_request',
                subject_id=config_request_id,
                property_name='customer_segment',
                asserted_value=segment,
                value_type='string',
                source_system=source_system,
                source_actor_id=None,
                source_actor_role='process',
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                arrival_at=arrival_at,
                simulator_classification=simulator_classification,
                evidence_lineage={
                    'event_type': 'CONFIGURATION_REQUESTED',
                    'mapping_id': 'CONF_REQ_SEGMENT',
                    'source_path': 'payload.segment',
                    'raw_event_id': raw_event_id,
                }
            ))

        return rows

    def get_all_evidence(self) -> List[EvidenceRow]:
        """Return all generated Evidence rows"""
        return self.evidence_rows

    def get_evidence_by_event_type(self, event_type: str) -> List[EvidenceRow]:
        """Get Evidence rows by event type"""
        return [e for e in self.evidence_rows if 'PRODUCT_DEFINED' in e.mapping_id if 'PRODUCT_DEFINED' in event_type
                or 'CONFIGURATION_REQUESTED' in event_type and 'PRODUCT_DEFINED' not in e.mapping_id]

    def get_summary(self) -> Dict[str, Any]:
        """Get transformation summary"""
        product_def_rows = [e for e in self.evidence_rows if 'PRODUCT_DEF' in e.mapping_id]
        conf_req_rows = [e for e in self.evidence_rows if 'CONF_REQ' in e.mapping_id]

        return {
            'total_evidence_rows': len(self.evidence_rows),
            'product_defined_rows': len(product_def_rows),
            'configuration_requested_rows': len(conf_req_rows),
            'processed_raw_events': len(self.processed_raw_ids),
            'breakdown_by_mapping': self._count_by_mapping(),
        }

    def _count_by_mapping(self) -> Dict[str, int]:
        """Count Evidence rows by mapping_id"""
        counts = {}
        for e in self.evidence_rows:
            counts[e.mapping_id] = counts.get(e.mapping_id, 0) + 1
        return counts
