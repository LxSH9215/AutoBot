import yaml
import os
from datetime import datetime

FEEDBACK_LOG = "feedback_log.yaml"

def log_feedback(comment_id, action, rule_id):
    feedback = {
        'comment_id': comment_id,
        'action': action,
        'rule_id': rule_id,
        'timestamp': datetime.now().isoformat()
    }
    
    # Load existing feedback
    feedback_data = []
    if os.path.exists(FEEDBACK_LOG):
        with open(FEEDBACK_LOG, 'r') as f:
            feedback_data = yaml.safe_load(f) or []
    
    # Add new feedback
    feedback_data.append(feedback)
    
    # Save to file
    with open(FEEDBACK_LOG, 'w') as f:
        yaml.dump(feedback_data, f)
    
    # Adjust rule weights
    adjust_rule_weights(rule_id, action)

def adjust_rule_weights(rule_id, action):
    """Adjust rule weights based on feedback"""
    weight_change = {
        'resolve': 0.05,
        'dismiss': -0.1,
        'override': 0
    }.get(action, 0)
    
    if weight_change == 0:
        return
    
    # Update rule weights
    with open('config/rules.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    if rule_id in config['rule_weights']:
        new_weight = max(0.1, min(2.0, 
            config['rule_weights'][rule_id] + weight_change))
        config['rule_weights'][rule_id] = new_weight
    
    # Save updated weights
    with open('config/rules.yaml', 'w') as f:
        yaml.dump(config, f)