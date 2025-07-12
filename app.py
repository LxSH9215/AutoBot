import os
import re
import json
import hmac
import hashlib
import requests
import yaml
import base64
import traceback
from dotenv import load_dotenv
from flask import Flask, request
from threading import Thread

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Load rule weights
with open('config/rules.yaml') as f:
    RULE_WEIGHTS = yaml.safe_load(f)['rule_weights']

@app.route('/')
def home():
    return "AutoReviewBot is running! Use /webhook for GitHub events.", 200

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    print("\n===== WEBHOOK RECEIVED =====")
    print(f"Event: {request.headers.get('X-GitHub-Event')}")
    
    # Validate webhook secret
    secret = os.getenv('GITHUB_WEBHOOK_SECRET')
    if not secret:
        return "Webhook secret not configured", 500
    
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

def parse_diff(diff):
    """Parse GitHub diff to extract changed files"""
    files = []
    pattern = re.compile(r'^\+\+\+ b/(.*)$', re.MULTILINE)
    for match in pattern.finditer(diff):
        file_path = match.group(1)
        # Only consider Java files
        if file_path.endswith('.java'):
            files.append({'path': file_path})
    return files

def get_file_content(repo, path, sha):
    """Fetch file content from GitHub"""
    headers = {'Authorization': f'token {os.getenv("GITHUB_TOKEN")}'}
    url = f'https://api.github.com/repos/{repo}/contents/{path}?ref={sha}'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        content_data = response.json()
        return base64.b64decode(content_data['content']).decode('utf-8')
    except Exception as e:
        print(f"Error fetching {path}: {str(e)}")
        return ""

def analyze_file(content, file_path):
    """Hybrid analysis of Java file"""
    violations = []
    
    # 1. Static analysis (fast)
    static_violations = analyze_static_rules(content)
    violations.extend(static_violations)
    
    # 2. LLM analysis for complex rules
    if should_analyze_with_llm(content):
        llm_violations = analyze_with_llm(content)
        violations.extend(llm_violations)
    
    return violations

def should_analyze_with_llm(content):
    """Determine if LLM analysis is needed"""
    return len(content) < 3000  # Only analyze small files with LLM

def calculate_compliance_score(violations, line_count):
    """Calculate file compliance score (0-10)"""
    if line_count == 0:
        return 10.0
        
    severity_score = sum(RULE_WEIGHTS.get(v['rule'], 0.5) for v in violations)
    normalized_score = min(severity_score / max(1, line_count / 50), 10)
    return max(0, 10 - normalized_score)

def calculate_overall_score(file_scores):
    """Calculate weighted overall compliance score"""
    if not file_scores:
        return 10.0
        
    total_score = sum(file_scores.values())
    return total_score / len(file_scores)

def generate_summary(compliance_score, violation_count, file_scores):
    """Generate PR summary with compliance score"""
    summary = f"## ⚙️ AutoReviewBot Report\n\n"
    summary += f"### 📊 Code Quality Compliance Score: {compliance_score:.1f}/10\n\n"
    summary += f"- **Total violations found**: {violation_count}\n"
    
    if file_scores:
        summary += "\n### 📝 File Scores:\n"
        for file, score in file_scores.items():
            summary += f"- `{file}`: {score:.1f}/10\n"
    
    summary += "\n### 🚦 Merge Status: "
    
    if compliance_score >= 8.0:
        summary += "✅ **APPROVED** (High quality)"
    elif compliance_score >= 6.0:
        summary += "⚠️ **CONDITIONAL APPROVAL** (Needs minor improvements)"
    else:
        summary += "❌ **REJECTED** (Critical issues found)"
    
    summary += "\n\n### 💬 Feedback Options:\n"
    summary += "1. ✅ Resolve - Mark violation as fixed\n"
    summary += "2. ❌ Dismiss - False positive (helps improve bot)\n"
    summary += "3. ⚠️ Override - Merge despite issues (maintainers only)"
    
    return summary

def format_comment(violation):
    """Format violation comment for GitHub"""
    rule_descriptions = {
        "G2": "Replace imperative code with lambdas/streams",
        "G3": "Avoid returning nulls - use Optional",
        "G4": "Protect mutable fields from external modification",
        "G6": "Use appropriate data structures",
        "G8": "Code to interfaces, not implementations",
        "G9": "Avoid unnecessary interface definitions",
        "G10": "Override hashCode when overriding equals"
    }
    
    rule_id = violation['rule']
    rule_desc = rule_descriptions.get(rule_id, rule_id)
    description = violation['description']
    suggestion = violation['suggestion']
    
    return (
        f"**⚠️ Rule Violation: {rule_desc}**  \n"
        f"{description}\n\n"
        f"**🧠 Suggested Fix:**\n"
        f"```java\n"
        f"{suggestion}\n"
        f"```\n\n"
        f"**🔧 Feedback Options:**\n"
        f"- ✅ `@bot resolve` - Mark as resolved\n"
        f"- ❌ `@bot dismiss` - False positive\n"
        f"- ⚠️ `@bot override` - Override (maintainers)\n\n"
        f"_Detected by AutoReviewBot [Rule: {rule_id}]_"
    )

def process_pr(pr_details):
    print(f"\n🚀 Processing PR #{pr_details['pr_number']} in {pr_details['repo']}")
    print(f"Commit SHA: {pr_details['commit_sha']}")
    print(f"Diff URL: {pr_details['diff_url']}")
    
    try:
        # Get PR diff with authentication
        headers = {'Authorization': f'token {os.getenv("GITHUB_TOKEN")}'}
        diff_response = requests.get(pr_details['diff_url'], headers=headers)
        diff_response.raise_for_status()
        diff = diff_response.text
        print(f"Fetched diff ({len(diff)} bytes)")
        
        changed_files = parse_diff(diff)
        print(f"Found {len(changed_files)} changed Java files")
        
        comments = []
        all_violations = []
        file_scores = {}
        
        for file in changed_files:
            print(f"Analyzing {file['path']}")
            content = get_file_content(pr_details['repo'], file['path'], pr_details['commit_sha'])
            
            if not content:
                print(f"⚠️ Empty content for {file['path']}, skipping")
                continue
                
            violations = analyze_file(content, file['path'])
            all_violations.extend(violations)
            print(f"Found {len(violations)} violations in {file['path']}")
            
            # Calculate file compliance score
            line_count = len(content.split('\n'))
            file_score = calculate_compliance_score(violations, line_count)
            file_scores[file['path']] = file_score
            
            for violation in violations:
                comments.append({
                    'path': file['path'],
                    'line': violation['line'],
                    'body': format_comment(violation)
                })
        
        # Calculate overall compliance score
        compliance_score = calculate_overall_score(file_scores)
        print(f"Overall compliance score: {compliance_score:.1f}/10")
        
        # Create summary comment
        summary = generate_summary(compliance_score, len(all_violations), file_scores)
        print(f"Generated summary ({len(summary)} chars)")
        
        # Post review to GitHub
        post_review(pr_details, comments, summary)
        print("✅ PR processing completed")
        
    except Exception as e:
        print(f"\n❌ ERROR processing PR: {str(e)}")
        traceback.print_exc()

def post_review(pr_details, comments, summary):
    """Post review comments to GitHub (placeholder)"""
    print(f"\n📝 Would post review to PR #{pr_details['pr_number']}:")
    print(f"- Summary: {summary[:100]}...")
    print(f"- {len(comments)} individual comments")
    
    # Actual implementation would look like:
    """
    headers = {
        'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
        'Accept': 'application/vnd.github.v3+json'
    }
    url = f'https://api.github.com/repos/{pr_details["repo"]}/pulls/{pr_details["pr_number"]}/reviews'
    
    review = {
        'commit_id': pr_details['commit_sha'],
        'body': summary,
        'event': 'COMMENT',
        'comments': comments
    }
    
    response = requests.post(url, json=review, headers=headers)
    response.raise_for_status()
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)