"""
Unit tests for Recon Plugins output parsers.
"""

import pytest

from app.models.asset import AssetType
from app.plugins.reconnaissance.amass.plugin import AmassPlugin
from app.plugins.reconnaissance.assetfinder.plugin import AssetfinderPlugin
from app.plugins.reconnaissance.subfinder.plugin import SubfinderPlugin


@pytest.fixture
def subfinder():
    return SubfinderPlugin(config={}, target="example.com")


@pytest.fixture
def amass():
    return AmassPlugin(config={}, target="example.com")


@pytest.fixture
def assetfinder():
    return AssetfinderPlugin(config={}, target="example.com")


@pytest.mark.unit
def test_subfinder_parser(subfinder: SubfinderPlugin):
    raw_output = '{"host":"api.example.com","ip":"1.2.3.4"}\n{"host":"dev.example.com"}\n'
    results = subfinder.parse_results(raw_output)
    
    assert len(results.assets) == 2
    assert results.assets[0].value == "api.example.com"
    assert results.assets[0].source_tool == "subfinder"
    assert results.assets[0].asset_type == AssetType.DOMAIN
    assert len(results.vulnerabilities) == 0


@pytest.mark.unit
def test_subfinder_parser_handles_garbage(subfinder: SubfinderPlugin):
    raw_output = '{"host":"api.example.com"}\nnot a json string\n{"host":"dev.example.com"}'
    results = subfinder.parse_results(raw_output)
    
    assert len(results.assets) == 2


@pytest.mark.unit
def test_amass_parser(amass: AmassPlugin):
    raw_output = '{"name":"api.example.com","domain":"example.com"}\n{"name":"dev.example.com"}\n'
    results = amass.parse_results(raw_output)
    
    assert len(results.assets) == 2
    assert results.assets[0].value == "api.example.com"
    assert results.assets[0].source_tool == "amass"


@pytest.mark.unit
def test_assetfinder_parser(assetfinder: AssetfinderPlugin):
    raw_output = "api.example.com\ndev.example.com\n"
    results = assetfinder.parse_results(raw_output)
    
    assert len(results.assets) == 2
    assert results.assets[0].value == "api.example.com"
    assert results.assets[0].source_tool == "assetfinder"


@pytest.mark.unit
def test_assetfinder_parser_filters_garbage(assetfinder: AssetfinderPlugin):
    raw_output = "api.example.com\nnot_a_domain\n12345\nsub.example.com"
    results = assetfinder.parse_results(raw_output)
    
    # Should only pick up the valid looking domains
    assert len(results.assets) == 2
    assert results.assets[0].value == "api.example.com"
    assert results.assets[1].value == "sub.example.com"
