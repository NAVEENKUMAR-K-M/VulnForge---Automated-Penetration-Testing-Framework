import pytest
from app.utils.tech_mapper import categorize_technologies

def test_categorize_technologies():
    techs = ["WordPress", "PHP", "Nginx", "React", "UnknownTech"]
    structured = categorize_technologies(techs)
    
    assert "WordPress" in structured["cms"]
    assert "PHP" in structured["languages"]
    assert "Nginx" in structured["servers"]
    assert "React" in structured["frameworks"]

def test_categorize_technologies_empty():
    # Empty input yields no buckets — categorize_technologies omits empty
    # categories and returns sorted lists for populated ones.
    assert categorize_technologies([]) == {}
