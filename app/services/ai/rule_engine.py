"""
Rule Engine - Policy/rule execution engine

Evaluates conditions and executes actions on records.
This is a flexible rule engine that can work with any dict-like records.
"""

import re
import time
import logging
from typing import Any, Dict, List, Callable, Optional

from app.schemas.ai import PolicyDSL, PolicyCondition, PolicyAction, PolicyExecutionResult

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Evaluates conditions and executes actions on records.
    
    This is a flexible rule engine that can work with any dict-like records.
    Extend the OPERATORS and action_handlers for custom behavior.
    """
    
    # Operator functions - extend as needed
    OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
        'eq': lambda a, b: a == b,
        'neq': lambda a, b: a != b,
        'gt': lambda a, b: float(a) > float(b) if a is not None else False,
        'lt': lambda a, b: float(a) < float(b) if a is not None else False,
        'gte': lambda a, b: float(a) >= float(b) if a is not None else False,
        'lte': lambda a, b: float(a) <= float(b) if a is not None else False,
        'contains': lambda a, b: str(b).lower() in str(a).lower() if a else False,
        'not_contains': lambda a, b: str(b).lower() not in str(a).lower() if a else True,
        'starts_with': lambda a, b: str(a).lower().startswith(str(b).lower()) if a else False,
        'ends_with': lambda a, b: str(a).lower().endswith(str(b).lower()) if a else False,
        'between': lambda a, b: float(b[0]) <= float(a) <= float(b[1]) if a is not None and isinstance(b, list) and len(b) >= 2 else False,
        'in': lambda a, b: a in b if isinstance(b, list) else False,
        'not_in': lambda a, b: a not in b if isinstance(b, list) else True,
        'matches': lambda a, b: bool(re.match(str(b), str(a))) if a else False,
        'is_null': lambda a, b: a is None or a == '',
        'is_not_null': lambda a, b: a is not None and a != '',
    }
    
    def __init__(self):
        # Register action handlers
        self.action_handlers: Dict[str, Callable] = {
            'set_status': self._action_set_status,
            'set_field': self._action_set_field,
            'auto_approve': self._action_auto_approve,
            'auto_reject': self._action_auto_reject,
            'flag_review': self._action_flag_review,
            'add_note': self._action_add_note,
            'add_tag': self._action_add_tag,
            'notify': self._action_notify,
        }
    
    def register_action(self, action_type: str, handler: Callable):
        """Register a custom action handler."""
        self.action_handlers[action_type] = handler
    
    def get_field_value(self, record: Dict[str, Any], field: str, field_path: Optional[str] = None) -> Any:
        """Get a field value, supporting dot-notation for nested fields."""
        path = field_path or field
        
        if '.' in path:
            parts = path.split('.')
            value = record
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value
        
        return record.get(field)
    
    def evaluate_condition(self, record: Dict[str, Any], condition: PolicyCondition) -> bool:
        """Evaluates a single condition against a record."""
        field_value = self.get_field_value(record, condition.field, condition.field_path)
        
        operator_func = self.OPERATORS.get(condition.operator)
        if not operator_func:
            logger.warning(f"Unknown operator: {condition.operator}")
            return False
        
        try:
            return operator_func(field_value, condition.value)
        except (TypeError, ValueError) as e:
            logger.debug(f"Condition evaluation error: {e}")
            return False
    
    def apply_policy(
        self, 
        record: Dict[str, Any], 
        policy: PolicyDSL,
        policy_id: Optional[str] = None,
        policy_name: Optional[str] = None
    ) -> PolicyExecutionResult:
        """
        Applies a policy to a record.
        
        Returns:
            PolicyExecutionResult with match status and modifications
        """
        start_time = time.time()
        
        # Evaluate conditions based on match_mode
        if policy.match_mode == "any":
            all_match = any(
                self.evaluate_condition(record, cond) 
                for cond in policy.conditions
            )
        else:  # "all" - default AND logic
            all_match = all(
                self.evaluate_condition(record, cond) 
                for cond in policy.conditions
            )
        
        if not all_match:
            return PolicyExecutionResult(
                matched=False,
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # Execute all actions
        result_record = record.copy()
        actions_applied = []
        modified_fields = {}
        
        for action in policy.actions:
            handler = self.action_handlers.get(action.type)
            if handler:
                changes = handler(result_record, action)
                if changes:
                    modified_fields.update(changes)
                    actions_applied.append(action.type)
            else:
                logger.warning(f"Unknown action type: {action.type}")
        
        return PolicyExecutionResult(
            matched=True,
            policy_id=policy_id,
            policy_name=policy_name,
            actions_applied=actions_applied,
            modified_fields=modified_fields,
            execution_time_ms=(time.time() - start_time) * 1000
        )
    
    # Action handlers
    def _action_set_status(self, record: Dict, action: PolicyAction) -> Dict:
        record['status'] = action.value
        return {'status': action.value}
    
    def _action_set_field(self, record: Dict, action: PolicyAction) -> Dict:
        if action.params and 'field' in action.params:
            field = action.params['field']
            record[field] = action.value
            return {field: action.value}
        return {}
    
    def _action_auto_approve(self, record: Dict, action: PolicyAction) -> Dict:
        record['status'] = 'approved'
        record['auto_processed'] = True
        return {'status': 'approved', 'auto_processed': True}
    
    def _action_auto_reject(self, record: Dict, action: PolicyAction) -> Dict:
        record['status'] = 'rejected'
        record['auto_processed'] = True
        return {'status': 'rejected', 'auto_processed': True}
    
    def _action_flag_review(self, record: Dict, action: PolicyAction) -> Dict:
        record['needs_review'] = True
        record['review_reason'] = action.value or 'Flagged by policy'
        return {'needs_review': True, 'review_reason': record['review_reason']}
    
    def _action_add_note(self, record: Dict, action: PolicyAction) -> Dict:
        notes = record.get('notes', [])
        if isinstance(notes, list):
            notes.append(action.value)
        else:
            notes = [action.value]
        record['notes'] = notes
        return {'notes': notes}
    
    def _action_add_tag(self, record: Dict, action: PolicyAction) -> Dict:
        tags = record.get('tags', [])
        if isinstance(tags, list) and action.value not in tags:
            tags.append(action.value)
        record['tags'] = tags
        return {'tags': tags}
    
    def _action_notify(self, record: Dict, action: PolicyAction) -> Dict:
        record['notification_pending'] = True
        record['notification_message'] = action.value
        return {'notification_pending': True}


# Singleton instance
rule_engine = RuleEngine()

