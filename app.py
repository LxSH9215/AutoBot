import os
import re
import json
import hmac
import hashlib
import requests
from flask import Flask, request
from threading import Thread
from static_analyzer import analyze_static_rules
from llm_analyzer import analyze_with_llm
from feedback import log_feedback, adjust_rule_weights

app = Flask(__name__)

# Load rule weights
with open('config/rules.yaml') as f:
    RULE_WEIGHTS = yaml.safe_load(f)['rule_weights']

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Verify signature
    secret = os.getenv('GITHUB_WEBHOOK_SECRET')
    signature = request.headers.get('X-Hub-Signature-256', '')
    body = request.data
    computed_hash = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(computed_hash, signature):
        return "Invalid signature", 401
    
    payload = request.json
    event = request.headers.get('X-GitHub-Event')
    
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        pr_details = {
            'repo': payload['repository']['full_name'],
            'pr_number': payload['number'],
            'commit_sha': payload['pull_request']['head']['sha'],
            'diff_url': payload['pull_request']['diff_url'],
            'action': payload['action']
        }
        Thread(target=process_pr, args=(pr_details,)).start()
        return 'PR processing started', 202
    
    return 'Event ignored', 200

def process_pr(pr_details):
    # Get PR diff
    diff = requests.get(pr_details['diff_url']).text
    changed_files = parse_diff(diff)
    
    comments = []
    all_violations = []
    file_scores = {}
    
    for file in changed_files:
        if not file['path'].endswith('.java'):
            continue
            
        content = get_file_content(pr_details['repo'], file['path'], pr_details['commit_sha'])
        violations = analyze_file(content, file['path'])
        all_violations.extend(violations)
        
        # Calculate file compliance score
        file_score = calculate_compliance_score(violations, len(content.split('\n')))
        file_scores[file['path']] = file_score
        
        for violation in violations:
            comments.append({
                'path': file['path'],
                'line': violation['line'],
                'body': format_comment(violation)
            })
    
    # Calculate overall compliance score
    compliance_score = calculate_overall_score(file_scores)
    
    # Create summary comment
    summary = generate_summary(compliance_score, len(all_violations), file_scores)
    
    # Post review to GitHub
    post_review(pr_details, comments, summary)

# Helper functions (parse_diff, get_file_content, etc.) go here
# ... [Implementation from previous response] ...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)