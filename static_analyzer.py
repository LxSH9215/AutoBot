import re

RULE_DESCRIPTIONS = {
    "G3": "Avoid returning nulls - use Optional",
    "G4": "Protect mutable fields from external modification",
    "G6": "Use appropriate data structures",
    "G8": "Code to interfaces, not implementations",
    "G10": "Override hashCode when overriding equals"
}

RULE_SUGGESTIONS = {
    "G3": "return Optional.empty();",
    "G4": "this.field = new ArrayList<>(input);",
    "G6": "Replace with {replacement}",
    "G8": "Use {interface} interface instead",
    "G10": "@Override\npublic int hashCode() {{\n    return Objects.hash(field1, field2);\n}}"
}

def analyze_static_rules(content):
    violations = []
    
    # G3: Null return check
    for match in re.finditer(r'public\s+(\w+)\s+\w+\s*\([^)]*\)\s*\{[^}]*return\s+null;', content):
        line = content[:match.start()].count('\n') + 1
        violations.append({
            'rule': 'G3',
            'line': line,
            'description': RULE_DESCRIPTIONS['G3'],
            'suggestion': RULE_SUGGESTIONS['G3']
        })
    
    # G4: Mutable field assignment
    for match in re.finditer(r'this\.\w+\s*=\s*\w+;', content):
        line = content[:match.start()].count('\n') + 1
        violations.append({
            'rule': 'G4',
            'line': line,
            'description': RULE_DESCRIPTIONS['G4'],
            'suggestion': RULE_SUGGESTIONS['G4']
        })
    
    # G10: equals/hashCode contract
    if 'public boolean equals(' in content and 'public int hashCode(' not in content:
        line = content.index('public boolean equals(') + 1
        violations.append({
            'rule': 'G10',
            'line': line,
            'description': RULE_DESCRIPTIONS['G10'],
            'suggestion': RULE_SUGGESTIONS['G10']
        })
    
    return violations