"""
Utility for mapping raw technology strings into specific categories.
"""

from typing import Any

CMS_KEYWORDS = {"wordpress", "drupal", "joomla", "magento", "ghost", "wix", "squarespace", "typo3"}
FRAMEWORK_KEYWORDS = {"react", "angular", "vue", "django", "flask", "laravel", "spring", "express", "ruby on rails", "next.js", "nuxt", "bootstrap", "jquery", "tailwind"}
LANG_KEYWORDS = {"php", "python", "ruby", "java", "node.js", "go", "c#", "asp.net", "perl"}
SERVER_KEYWORDS = {"nginx", "apache", "iis", "caddy", "tomcat", "litespeed", "cloudflare", "aws", "envoy", "gunicorn"}

def categorize_technologies(tech_list: list[str]) -> dict[str, list[str]]:
    """
    Takes a flat list of technology strings and categorizes them.
    Returns a dictionary with keys: cms, frameworks, languages, servers.
    """
    structured = {
        "cms": set(),
        "frameworks": set(),
        "languages": set(),
        "servers": set(),
    }
    
    for tech in tech_list:
        if not isinstance(tech, str):
            continue
            
        t_lower = tech.lower()
        
        # Determine category by checking substring matches
        matched = False
        
        for kw in CMS_KEYWORDS:
            if kw in t_lower:
                structured["cms"].add(tech)
                matched = True
                break
                
        if not matched:
            for kw in FRAMEWORK_KEYWORDS:
                if kw in t_lower:
                    structured["frameworks"].add(tech)
                    matched = True
                    break
                    
        if not matched:
            for kw in LANG_KEYWORDS:
                if kw in t_lower:
                    structured["languages"].add(tech)
                    matched = True
                    break
                    
        if not matched:
            for kw in SERVER_KEYWORDS:
                if kw in t_lower:
                    structured["servers"].add(tech)
                    matched = True
                    break
                    
    # Convert sets back to sorted lists
    return {k: sorted(list(v)) for k, v in structured.items() if v}
