"""Capability definitions for WebCMD workers."""
from __future__ import annotations
from webcmd.state.enums import RiskLevel

# Standard capability catalog with default risk levels
CAPABILITY_RISK_MAP: dict[str, RiskLevel] = {
    # Browser - Read
    "browser.navigate": RiskLevel.LOW,
    "browser.dom_inspect": RiskLevel.LOW,
    "browser.screenshot": RiskLevel.LOW,
    "browser.scroll": RiskLevel.LOW,
    "browser.wait": RiskLevel.LOW,
    # Browser - Write
    "browser.click": RiskLevel.MEDIUM,
    "browser.type": RiskLevel.MEDIUM,
    "browser.download": RiskLevel.MEDIUM,
    "browser.upload": RiskLevel.HIGH,
    "browser.submit_form": RiskLevel.HIGH,
    "browser.purchase": RiskLevel.CRITICAL,
    # API
    "api.get": RiskLevel.LOW,
    "api.post": RiskLevel.MEDIUM,
    "api.put": RiskLevel.MEDIUM,
    "api.delete": RiskLevel.HIGH,
    # Filesystem
    "filesystem.read": RiskLevel.LOW,
    "filesystem.list": RiskLevel.LOW,
    "filesystem.exists": RiskLevel.LOW,
    "filesystem.write": RiskLevel.MEDIUM,
    "filesystem.rename": RiskLevel.MEDIUM,
    "filesystem.delete": RiskLevel.HIGH,
    # Shell
    "shell.execute": RiskLevel.HIGH,
}


def get_risk_level(capability: str) -> RiskLevel:
    """Get the default risk level for a capability."""
    return CAPABILITY_RISK_MAP.get(capability, RiskLevel.MEDIUM)
