"""
Financial Advisor — Stage 2: Asset Classification & Advanced Tax Logic

Enhanced retirement planning tool with:
- Asset classification (pre_tax, post_tax, tax_deferred)
- Per-asset growth simulation
- Sophisticated tax logic with IRS projections
- Capital gains calculations for brokerage accounts

USAGE:
  # 1) Run tests
  python fin_advisor.py --run-tests

  # 2) CLI with flags (no UI)
  python fin_advisor.py \
    --age 30 --retirement-age 65 \
    --income 85000 --contribution-rate 15 \
    --current-balance 50000 --growth-rate 7 \
    --inflation-rate 3 --tax-rate 25

  # 3) Streamlit (if installed)
  streamlit run fin_advisor.py

Author: AI Assistant
Version: 3.1.0
"""

from __future__ import annotations
import argparse
import math
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

# Version Management
VERSION = "3.1.0"

def bump_minor_version(version: str) -> str:
    """Bump the minor version number (e.g., 2.1.0 -> 2.2.0)."""
    parts = version.split('.')
    if len(parts) >= 2:
        major, minor = parts[0], parts[1]
        patch = parts[2] if len(parts) > 2 else "0"
        new_minor = str(int(minor) + 1)
        return f"{major}.{new_minor}.{patch}"
    return version

# Streamlit import
import streamlit as st
import io
import csv
from datetime import datetime

import pandas as pd

# n8n integration for financial statement upload
try:
    from integrations.n8n_client import N8NClient, N8NError
    from pypdf import PdfReader
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
    _N8N_AVAILABLE = True
except ImportError:
    _N8N_AVAILABLE = False

# PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False

# ---------------------------
# Domain Models & Computation
# ---------------------------

class AssetType(Enum):
    """Asset classification for tax treatment."""
    PRE_TAX = "pre_tax"           # 401(k), Traditional IRA
    POST_TAX = "post_tax"         # Roth IRA, Brokerage
    TAX_DEFERRED = "tax_deferred" # Annuities, HSA

@dataclass
class Asset:
    """Individual asset with specific tax treatment."""
    name: str
    asset_type: AssetType
    current_balance: float
    annual_contribution: float
    growth_rate_pct: float
    tax_rate_pct: float = 0.0  # For post_tax assets (capital gains)
    
    def __post_init__(self):
        """Validate asset configuration."""
        if self.asset_type == AssetType.POST_TAX and self.tax_rate_pct == 0.0:
            # Default capital gains rate for brokerage accounts
            self.tax_rate_pct = 15.0

@dataclass
class TaxBracket:
    """IRS tax bracket information."""
    min_income: float
    max_income: Optional[float]
    rate_pct: float

@dataclass
class UserInputs:
    age: int
    retirement_age: int
    life_expectancy: int  # Expected age at death
    annual_income: float
    contribution_rate_pct: float  # % of income contributed annually
    expected_growth_rate_pct: float  # nominal annual return %
    inflation_rate_pct: float
    current_marginal_tax_rate_pct: float  # Current tax bracket
    retirement_marginal_tax_rate_pct: float  # Projected retirement tax bracket
    assets: List[Asset] = field(default_factory=list)
    
    # Legacy support
    @property
    def current_balance(self) -> float:
        """Total current balance across all assets."""
        return sum(asset.current_balance for asset in self.assets)
    
    @property
    def asset_types(self) -> List[str]:
        """Legacy asset types for backward compatibility."""
        return [asset.name for asset in self.assets]


def years_to_retirement(age: int, retirement_age: int) -> int:
    if retirement_age < age:
        raise ValueError("retirement_age must be >= age")
    return retirement_age - age


def future_value_with_contrib(principal: float, annual_contribution: float, rate_pct: float, years: int) -> float:
    """Compute FV with annual compounding and end-of-year contributions.
    Handles zero-rate edge case explicitly.
    FV = P*(1+r)^t + C * [((1+r)^t - 1)/r]
    """
    if years < 0:
        raise ValueError("years must be >= 0")
    r = rate_pct / 100.0
    if r == 0:
        return principal + annual_contribution * years
    growth = (1.0 + r) ** years
    return principal * growth + annual_contribution * ((growth - 1.0) / r)


def get_irs_tax_brackets_2024() -> List[TaxBracket]:
    """Get 2024 IRS tax brackets for single filers."""
    return [
        TaxBracket(0, 11000, 10.0),
        TaxBracket(11000, 44725, 12.0),
        TaxBracket(44725, 95375, 22.0),
        TaxBracket(95375, 182050, 24.0),
        TaxBracket(182050, 231250, 32.0),
        TaxBracket(231250, 578125, 35.0),
        TaxBracket(578125, None, 37.0),
    ]


def project_tax_rate(income: float, brackets: List[TaxBracket]) -> float:
    """Project marginal tax rate based on income and tax brackets."""
    for bracket in brackets:
        if bracket.min_income <= income and (bracket.max_income is None or income < bracket.max_income):
            return bracket.rate_pct
    return brackets[-1].rate_pct  # Top bracket


def calculate_asset_growth(asset: Asset, years: int) -> Tuple[float, float]:
    """Calculate future value and total contributions for an asset.
    
    Returns:
        Tuple of (future_value, total_contributions)
    """
    fv = future_value_with_contrib(
        asset.current_balance,
        asset.annual_contribution,
        asset.growth_rate_pct,
        years
    )
    total_contributions = asset.annual_contribution * years
    return fv, total_contributions


def apply_tax_logic(asset: Asset, future_value: float, total_contributions: float, 
                   retirement_tax_rate_pct: float) -> Tuple[float, float]:
    """Apply tax logic based on asset type.
    
    Returns:
        Tuple of (after_tax_value, tax_liability)
    """
    # Handle both enum and string asset types for robustness
    asset_type = asset.asset_type
    if hasattr(asset_type, 'value'):
        asset_type_value = asset_type.value
    else:
        asset_type_value = str(asset_type)
    
    if asset_type == AssetType.PRE_TAX or asset_type_value == "pre_tax":
        # Pre-tax accounts: taxed at withdrawal
        tax_liability = future_value * (retirement_tax_rate_pct / 100.0)
        after_tax_value = future_value - tax_liability
        
    elif asset_type == AssetType.POST_TAX or asset_type_value == "post_tax":
        if "Roth" in asset.name:
            # Roth IRA: no tax on withdrawal
            after_tax_value = future_value
            tax_liability = 0.0
        else:
            # Brokerage: only capital gains are taxed
            gains = future_value - total_contributions
            tax_liability = gains * (asset.tax_rate_pct / 100.0)
            after_tax_value = future_value - tax_liability
            
    elif asset_type == AssetType.TAX_DEFERRED or asset_type_value == "tax_deferred":
        # Annuities, HSA: complex rules, simplified for now
        if "HSA" in asset.name:
            # HSA: tax-free for medical expenses, taxed for other withdrawals
            # Simplified: assume 50% medical, 50% other
            medical_portion = future_value * 0.5
            other_portion = future_value * 0.5
            tax_liability = other_portion * (retirement_tax_rate_pct / 100.0)
            after_tax_value = future_value - tax_liability
        else:
            # Annuities: taxed as ordinary income
            tax_liability = future_value * (retirement_tax_rate_pct / 100.0)
            after_tax_value = future_value - tax_liability
    else:
        raise ValueError(f"Unknown asset type: {asset.asset_type} (type: {type(asset.asset_type)}, value: {asset_type_value})")
    
    return after_tax_value, tax_liability


def simple_post_tax(balance: float, tax_rate_pct: float) -> float:
    """Legacy function for backward compatibility."""
    tax_rate = tax_rate_pct / 100.0
    tax_rate = min(max(tax_rate, 0.0), 1.0)
    return balance * (1.0 - tax_rate)


def project(inputs: UserInputs) -> Dict[str, float]:
    """Enhanced projection with asset classification and sophisticated tax logic."""
    yrs = years_to_retirement(inputs.age, inputs.retirement_age)
    
    # If no assets defined, create a default one for backward compatibility
    if not inputs.assets:
        total_contribution = inputs.annual_income * (inputs.contribution_rate_pct / 100.0)
        default_asset = Asset(
            name="401(k) / Traditional IRA (Pre-Tax)",
            asset_type=AssetType.PRE_TAX,
            current_balance=inputs.current_balance,
            annual_contribution=total_contribution,
            growth_rate_pct=inputs.expected_growth_rate_pct
        )
        inputs.assets = [default_asset]
    
    # Calculate projections for each asset
    asset_results = []
    total_pre_tax_value = 0.0
    total_after_tax_value = 0.0
    total_tax_liability = 0.0
    
    for asset in inputs.assets:
        future_value, total_contributions = calculate_asset_growth(asset, yrs)
        after_tax_value, tax_liability = apply_tax_logic(
            asset, future_value, total_contributions, 
            inputs.retirement_marginal_tax_rate_pct
        )
        
        asset_results.append({
            "name": asset.name,
            "type": asset.asset_type.value,
            "pre_tax_value": future_value,
            "after_tax_value": after_tax_value,
            "tax_liability": tax_liability,
            "total_contributions": total_contributions
        })
        
        total_pre_tax_value += future_value
        total_after_tax_value += after_tax_value
        total_tax_liability += tax_liability
    
    # Calculate tax efficiency
    tax_efficiency = (total_after_tax_value / total_pre_tax_value * 100) if total_pre_tax_value > 0 else 0

    result = {
        "Years Until Retirement": float(yrs),
        "Total Future Value (Pre-Tax)": float(round(total_pre_tax_value, 2)),
        "Total After-Tax Balance": float(round(total_after_tax_value, 2)),
        "Total Tax Liability": float(round(total_tax_liability, 2)),
        "Tax Efficiency (%)": float(round(tax_efficiency, 2)),
        "Number of Assets": len(inputs.assets),
        "asset_results": asset_results,  # Store detailed breakdown for display
        "assets_input": inputs.assets  # Store input assets for current balance
    }

    # Add per-asset breakdown
    for i, asset_result in enumerate(asset_results):
        result[f"Asset {i+1} - {asset_result['name']} (Pre-Tax)"] = round(asset_result['pre_tax_value'], 2)
        result[f"Asset {i+1} - {asset_result['name']} (After-Tax)"] = round(asset_result['after_tax_value'], 2)

    return result


# ---------------------------
# UI LAYERS
# ---------------------------

_DEF_ASSET_TYPES = [
    ("401(k) / Traditional IRA", AssetType.PRE_TAX),
    ("Roth IRA", AssetType.POST_TAX),
    ("Brokerage Account", AssetType.POST_TAX),
    ("HSA (Health Savings Account)", AssetType.TAX_DEFERRED),
    ("Annuity", AssetType.TAX_DEFERRED),
    ("Savings Account", AssetType.POST_TAX),
]

def create_default_assets() -> List[Asset]:
    """Create default asset configuration."""
    return [
        Asset(
            name="401(k) / Traditional IRA",
            asset_type=AssetType.PRE_TAX,
            current_balance=50000,
            annual_contribution=12000,
            growth_rate_pct=7.0
        ),
        Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=10000,
            annual_contribution=6000,
            growth_rate_pct=7.0
        ),
        Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=15000,
            annual_contribution=3000,
            growth_rate_pct=7.0,
            tax_rate_pct=15.0  # Capital gains rate
        ),
        Asset(
            name="High-Yield Savings Account",
            asset_type=AssetType.POST_TAX,
            current_balance=25000,
            annual_contribution=2000,
            growth_rate_pct=4.5,
            tax_rate_pct=0.0  # Interest taxed as ordinary income, but no capital gains
        )
    ]


def create_asset_template_csv() -> str:
    """Create a CSV template for asset configuration."""
    template_data = [
        {
            "Account Name": "401(k) / Traditional IRA",
            "Asset Type": "pre_tax",
            "Current Balance": 50000,
            "Annual Contribution": 12000,
            "Growth Rate (%)": 7.0,
            "Tax Rate (%)": 0.0
        },
        {
            "Account Name": "Roth IRA",
            "Asset Type": "post_tax",
            "Current Balance": 10000,
            "Annual Contribution": 6000,
            "Growth Rate (%)": 7.0,
            "Tax Rate (%)": 0.0
        },
        {
            "Account Name": "Brokerage Account",
            "Asset Type": "post_tax",
            "Current Balance": 15000,
            "Annual Contribution": 3000,
            "Growth Rate (%)": 7.0,
            "Tax Rate (%)": 15.0
        },
        {
            "Account Name": "High-Yield Savings Account",
            "Asset Type": "post_tax",
            "Current Balance": 25000,
            "Annual Contribution": 2000,
            "Growth Rate (%)": 4.5,
            "Tax Rate (%)": 0.0
        }
    ]
    
    # Create CSV string
    output = io.StringIO()
    fieldnames = ["Account Name", "Asset Type", "Current Balance", "Annual Contribution", "Growth Rate (%)", "Tax Rate (%)"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(template_data)
    
    return output.getvalue()


def parse_uploaded_csv(csv_content: str) -> List[Asset]:
    """Parse uploaded CSV content into Asset objects."""
    assets = []
    
    try:
        # Read CSV content
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        for row in csv_reader:
            # Validate required fields
            required_fields = ["Account Name", "Asset Type", "Current Balance", "Annual Contribution", "Growth Rate (%)"]
            for field in required_fields:
                if field not in row or not row[field].strip():
                    raise ValueError(f"Missing or empty required field: {field}")
            
            # Parse asset type
            asset_type_str = row["Asset Type"].strip().lower()
            if asset_type_str == "pre_tax":
                asset_type = AssetType.PRE_TAX
            elif asset_type_str == "post_tax":
                asset_type = AssetType.POST_TAX
            elif asset_type_str == "tax_deferred":
                asset_type = AssetType.TAX_DEFERRED
            else:
                raise ValueError(f"Invalid asset type: {asset_type_str}. Must be 'pre_tax', 'post_tax', or 'tax_deferred'")
            
            # Parse numeric values (handle commas in numbers)
            try:
                def parse_number(value_str):
                    """Parse a number string, removing commas and handling empty values."""
                    if not value_str or value_str.strip() == '':
                        return 0.0
                    # Remove commas and convert to float
                    return float(value_str.replace(',', ''))
                
                current_balance = parse_number(row["Current Balance"])
                annual_contribution = parse_number(row["Annual Contribution"])
                growth_rate = parse_number(row["Growth Rate (%)"])
                tax_rate = parse_number(row.get("Tax Rate (%)", 0))
            except ValueError as e:
                raise ValueError(f"Invalid numeric value in row: {e}")
            
            # Validate ranges
            if current_balance < 0:
                raise ValueError("Current Balance cannot be negative")
            if annual_contribution < 0:
                raise ValueError("Annual Contribution cannot be negative")
            if growth_rate < 0 or growth_rate > 50:
                raise ValueError("Growth Rate must be between 0% and 50%")
            if tax_rate < 0 or tax_rate > 50:
                raise ValueError("Tax Rate must be between 0% and 50%")
            
            # Create asset
            asset = Asset(
                name=row["Account Name"].strip(),
                asset_type=asset_type,
                current_balance=current_balance,
                annual_contribution=annual_contribution,
                growth_rate_pct=growth_rate,
                tax_rate_pct=tax_rate
            )
            
            assets.append(asset)
        
        if not assets:
            raise ValueError("No valid assets found in CSV")
        
        return assets
        
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")


def generate_pdf_report(result: Dict[str, float], assets: List[Asset], user_inputs: Dict) -> bytes:
    """Generate a comprehensive PDF report of the retirement analysis."""
    if not _REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        textColor=colors.darkgreen
    )
    
    # Build PDF content
    story = []
    
    # Title
    client_name = user_inputs.get('client_name', 'Client')
    story.append(Paragraph(f"Retirement Planning Analysis Report", title_style))
    story.append(Paragraph(f"Prepared for: {client_name}", 
                          ParagraphStyle('ClientName', parent=styles['Heading2'], fontSize=16, alignment=TA_CENTER, textColor=colors.darkgreen)))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Legal Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.red,
        alignment=TA_LEFT,
        spaceAfter=12,
        borderWidth=1,
        borderColor=colors.red,
        borderPadding=6
    )
    
    story.append(Paragraph("IMPORTANT LEGAL DISCLAIMER", 
                          ParagraphStyle('DisclaimerTitle', parent=styles['Heading3'], fontSize=12, textColor=colors.red, alignment=TA_CENTER)))
    story.append(Paragraph(
        "This report provides educational and informational content only. It is NOT financial, tax, legal, or investment advice. "
        "Results are based on general assumptions and may not be suitable for your specific situation. "
        "Past performance does not guarantee future results; all projections are estimates. "
        "Always consult with qualified financial advisors, tax professionals, and legal counsel before making financial decisions. "
        "You are solely responsible for your financial decisions and their consequences. "
        "The creators and operators of this application disclaim all liability for any losses, damages, or consequences arising from the use of this information. "
        "By using this report, you acknowledge and agree to these terms.",
        disclaimer_style
    ))
    story.append(Spacer(1, 20))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    
    summary_data = [
        ["Metric", "Value"],
        ["Years Until Retirement", f"{result.get('Years Until Retirement', 0):.0f} years"],
        ["Total Future Value (Pre-Tax)", f"${result.get('Total Future Value (Pre-Tax)', 0):,.0f}"],
        ["Total After-Tax Balance", f"${result.get('Total After-Tax Balance', 0):,.0f}"],
        ["Total Tax Liability", f"${result.get('Total Tax Liability', 0):,.0f}"],
        ["Tax Efficiency", f"{result.get('Tax Efficiency (%)', 0):.1f}%"]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Portfolio Breakdown
    story.append(Paragraph("Portfolio Breakdown", heading_style))
    
    # Asset details table
    asset_data = [["Account", "Type", "Current Balance", "Annual Contribution", "Growth Rate", "Tax Rate"]]
    for asset in assets:
        asset_data.append([
            asset.name,
            asset.asset_type.value.replace('_', ' ').title(),
            f"${asset.current_balance:,.0f}",
            f"${asset.annual_contribution:,.0f}",
            f"{asset.growth_rate_pct}%",
            f"{asset.tax_rate_pct}%" if asset.tax_rate_pct > 0 else "N/A"
        ])
    
    asset_table = Table(asset_data, colWidths=[2*inch, 1*inch, 1.2*inch, 1.2*inch, 0.8*inch, 0.8*inch])
    asset_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9)
    ]))
    
    story.append(asset_table)
    story.append(Spacer(1, 20))
    
    # Individual Asset Results
    story.append(Paragraph("Individual Asset Projections", heading_style))
    
    # Find individual asset results
    asset_results = []
    for key, value in result.items():
        if "Asset" in key and "After-Tax" in key:
            asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
            asset_results.append([asset_name, f"${value:,.0f}"])
    
    if asset_results:
        asset_results_data = [["Account", "After-Tax Value at Retirement"]]
        asset_results_data.extend(asset_results)
        
        results_table = Table(asset_results_data, colWidths=[3*inch, 2*inch])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(results_table)
        story.append(Spacer(1, 20))
    
    # Retirement Income Analysis
    story.append(Paragraph("Retirement Income Analysis", heading_style))
    
    total_after_tax = result.get("Total After-Tax Balance", 0)
    life_expectancy = user_inputs.get('life_expectancy', 85)
    retirement_age = user_inputs.get('retirement_age', 65)
    years_in_retirement = life_expectancy - retirement_age
    annual_retirement_income = total_after_tax / years_in_retirement
    retirement_income_goal = user_inputs.get('retirement_income_goal', 0)
    income_shortfall = retirement_income_goal - annual_retirement_income
    income_ratio = (annual_retirement_income / retirement_income_goal * 100) if retirement_income_goal > 0 else 0
    
    income_data = [
        ["Metric", "Value"],
        ["Projected Annual Retirement Income", f"${annual_retirement_income:,.0f}"],
        ["Desired Annual Retirement Income", f"${retirement_income_goal:,.0f}"],
        ["Annual Shortfall/Surplus", f"${income_shortfall:,.0f}"],
        ["Income Goal Achievement", f"{income_ratio:.1f}%"]
    ]
    
    income_table = Table(income_data, colWidths=[3*inch, 2*inch])
    income_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(income_table)
    story.append(Spacer(1, 20))
    
    # Tax Analysis
    story.append(Paragraph("Tax Analysis", heading_style))
    
    tax_liability = result.get("Total Tax Liability", 0)
    total_pre_tax = result.get("Total Future Value (Pre-Tax)", 1)
    tax_percentage = (tax_liability / total_pre_tax * 100) if total_pre_tax > 0 else 0
    tax_efficiency = result.get("Tax Efficiency (%)", 0)
    
    tax_analysis = f"""
    <b>Tax Efficiency Rating:</b> {tax_efficiency:.1f}%<br/>
    <b>Total Tax Liability:</b> ${tax_liability:,.0f}<br/>
    <b>Tax as % of Pre-Tax Value:</b> {tax_percentage:.1f}%<br/>
    <b>Current Marginal Tax Rate:</b> {user_inputs.get('current_marginal_tax_rate_pct', 0)}%<br/>
    <b>Projected Retirement Tax Rate:</b> {user_inputs.get('retirement_marginal_tax_rate_pct', 0)}%
    """
    
    story.append(Paragraph(tax_analysis, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Recommendations
    story.append(Paragraph("Recommendations", heading_style))
    
    recommendations = []
    tax_percentage = (result.get("Total Tax Liability", 0) / result.get("Total Future Value (Pre-Tax)", 1) * 100) if result.get("Total Future Value (Pre-Tax)", 0) > 0 else 0
    if tax_efficiency > 85:
        recommendations.append("🎉 <b>Excellent tax efficiency!</b> Your portfolio is well-optimized with minimal tax liability.")
    elif tax_efficiency > 75:
        recommendations.append(f"⚠️ <b>Good tax efficiency</b> ({tax_percentage:.1f}% tax burden), but there may be room for improvement. <i>Goal: Lower this percentage by shifting assets to tax-advantaged accounts.</i>")
        recommendations.append("💡 <b>Tax Optimization Tips:</b>")
        recommendations.append("• Optimize asset location (taxable vs tax-advantaged accounts)")
        recommendations.append("• Consider Roth vs Traditional contributions based on tax rates")
        recommendations.append("• Maximize employer 401(k) match and HSA contributions")
        recommendations.append("• Use tax-loss harvesting and strategic withdrawal order")
    else:
        recommendations.append("🚨 <b>Consider tax optimization</b> strategies to improve efficiency.")
        recommendations.append("⚠️ <b>Priority Actions:</b>")
        recommendations.append("• Review asset allocation across account types")
        recommendations.append("• Maximize tax-advantaged contributions (401k, IRA, HSA)")
        recommendations.append("• Consider Roth conversions during low-income years")
        recommendations.append("• Switch to tax-efficient index funds")
    
    if len(assets) < 3:
        recommendations.append("💡 Consider diversifying across more account types for better tax optimization.")
    
    # Check for high-growth assets
    high_growth_assets = [a for a in assets if a.growth_rate_pct > 8]
    if high_growth_assets:
        recommendations.append("📈 You have high-growth assets - ensure proper risk management.")
    
    # Check for low-growth assets
    low_growth_assets = [a for a in assets if a.growth_rate_pct < 5]
    if low_growth_assets:
        recommendations.append("💰 Consider if low-growth assets align with your retirement timeline.")
    
    for rec in recommendations:
        story.append(Paragraph(rec, styles['Normal']))
        story.append(Spacer(1, 6))
    
    story.append(Spacer(1, 20))
    
    # Footer Disclaimer
    story.append(Paragraph("DISCLAIMER: This report is for educational purposes only and does not constitute professional financial advice. Consult qualified professionals before making financial decisions.", 
                          ParagraphStyle('FooterDisclaimer', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER, textColor=colors.red)))
    story.append(Spacer(1, 6))
    
    # Footer
    story.append(Paragraph("This report was generated by the Financial Advisor - Stage 2 application.", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# Streamlit UI - this runs when using 'streamlit run fin_advisor.py'
st.set_page_config(page_title="Financial Advisor - Stage 2", layout="wide")

# Initialize session state for onboarding flow
if 'onboarding_step' not in st.session_state:
    st.session_state.onboarding_step = 1
if 'onboarding_complete' not in st.session_state:
    st.session_state.onboarding_complete = False

# Initialize session state for form values
if 'birth_year' not in st.session_state:
    st.session_state.birth_year = datetime.now().year - 30
if 'retirement_age' not in st.session_state:
    st.session_state.retirement_age = 65
if 'life_expectancy' not in st.session_state:
    st.session_state.life_expectancy = 85
if 'annual_income' not in st.session_state:
    st.session_state.annual_income = 85000
if 'retirement_income_goal' not in st.session_state:
    st.session_state.retirement_income_goal = int(85000 * 0.75)
if 'client_name' not in st.session_state:
    st.session_state.client_name = ""
if 'assets' not in st.session_state:
    st.session_state.assets = []

# ==========================================
# SIDEBAR - Settings (Tax & Growth Assumptions)
# ==========================================
st.sidebar.title("⚙️ Settings")
st.sidebar.markdown("### Tax Settings")

# Current tax rate with helpful guidance
with st.sidebar.expander("💡 How to find your current tax rate", expanded=False):
    st.markdown("""
    **To find your current marginal tax rate:**
    1. **From your tax return**: Look at your most recent Form 1040, Line 15 (Taxable Income)
    2. **Use IRS tax brackets**: Find which bracket your income falls into

    **2024 Tax Brackets (Single):**
    - 10%: $0 - $11,600
    - 12%: $11,601 - $47,150
    - 22%: $47,151 - $100,525
    - 24%: $100,526 - $191,950
    - 32%: $191,951 - $243,725
    - 35%: $243,726 - $609,350
    - 37%: $609,351+
    """)

current_tax_rate = st.sidebar.slider("Current Marginal Tax Rate (%)", 0, 50, 22, help="Your current tax bracket based on your income")

with st.sidebar.expander("💡 How to estimate retirement tax rate", expanded=False):
    st.markdown("""
    **Consider these factors:**
    1. **Lower income**: Most people have lower income in retirement
    2. **Social Security**: Only 85% is taxable for most people
    3. **Roth withdrawals**: Tax-free if qualified
    4. **Required Minimum Distributions**: Start at age 73 (2024)

    **Common scenarios:**
    - **Conservative**: Same as current rate
    - **Optimistic**: 10-15% lower than current
    - **Pessimistic**: 5-10% higher (if tax rates increase)
    """)

retirement_tax_rate = st.sidebar.slider("Projected Retirement Tax Rate (%)", 0, 50, 25, help="Expected tax rate in retirement")

st.sidebar.markdown("---")
st.sidebar.markdown("### Growth Rate Assumptions")

with st.sidebar.expander("💡 Inflation guidance", expanded=False):
    st.markdown("""
    **Historical context:**
    - **Long-term average**: 3.0-3.5% annually
    - **Recent years**: 2-4% (2020-2024)
    - **Federal Reserve target**: 2% annually

    **Consider:**
    - **Conservative**: 2-3% (Fed target)
    - **Moderate**: 3-4% (historical average)
    - **Aggressive**: 4-5% (higher inflation)
    """)

inflation_rate = st.sidebar.slider("Expected Inflation Rate (%)", 0, 10, 3, help="Long-term inflation assumption (affects purchasing power)")

st.sidebar.markdown("---")
st.sidebar.markdown("**💡 Tip:** Adjust these settings anytime during the onboarding process.")

# Reset button (only show if onboarding is complete)
if st.session_state.onboarding_complete:
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Reset Onboarding", use_container_width=True):
        st.session_state.onboarding_step = 1
        st.session_state.onboarding_complete = False
        st.rerun()

# ==========================================
# MAIN AREA - Header & Disclaimer
# ==========================================
st.title("💰 Financial Advisor - Advanced Retirement Planning")

# Legal Disclaimer
with st.expander("⚠️ **IMPORTANT LEGAL DISCLAIMER**", expanded=False):
    st.markdown("""
    ### 🚨 **DISCLAIMER - READ CAREFULLY**

    **This application provides educational and informational content only. It is NOT financial, tax, legal, or investment advice.**

    **Important Limitations:**
    - **Not Professional Advice**: This tool is for educational purposes only and does not constitute professional financial, tax, legal, or investment advice
    - **No Personal Recommendations**: Results are based on general assumptions and may not be suitable for your specific situation
    - **No Guarantees**: Past performance does not guarantee future results; all projections are estimates
    - **Consult Professionals**: Always consult with qualified financial advisors, tax professionals, and legal counsel before making financial decisions
    - **Your Responsibility**: You are solely responsible for your financial decisions and their consequences

    **No Liability**: The creators and operators of this application disclaim all liability for any losses, damages, or consequences arising from the use of this information.

    **By using this application, you acknowledge and agree to these terms.**
    """)

# Collapsible description to reduce above-the-fold content
with st.expander("ℹ️ About This Application", expanded=False):
    st.markdown(
        """
        ### Stage 2: Asset Classification & Advanced Tax Logic
        This enhanced version includes:
        - **Asset Classification**: Pre-tax, Post-tax, and Tax-deferred accounts
        - **Per-Asset Growth Simulation**: Individual tracking of each account
        - **Sophisticated Tax Logic**: IRS tax brackets and capital gains calculations
        - **Tax Efficiency Analysis**: Optimize your retirement strategy
        """
    )

# ==========================================
# ONBOARDING FLOW - Progress Indicator
# ==========================================
st.markdown("---")

# Progress indicator
total_steps = 2
current_step = st.session_state.onboarding_step

# Visual progress bar
progress_text = f"**Step {current_step} of {total_steps}**"
progress_percentage = (current_step - 1) / total_steps
st.progress(progress_percentage, text=progress_text)

# Step titles
step_titles = {
    1: "👤 Personal Information",
    2: "🏦 Asset Configuration"
}

st.header(f"📝 {step_titles[current_step]}")
st.markdown("---")

# ==========================================
# STEP 1: Personal Information
# ==========================================
if current_step == 1:
    col1, col2 = st.columns(2)

    with col1:
        # Birth year input instead of age
        current_year = datetime.now().year
        birth_year = st.number_input(
            "Birth Year",
            min_value=current_year-90,
            max_value=current_year-18,
            value=st.session_state.birth_year,
            help="Your birth year (age will be calculated automatically)",
            key="birth_year_input"
        )
        st.session_state.birth_year = birth_year
        age = current_year - birth_year
        st.info(f"📅 **Current Age**: {age} years old")

        retirement_age = st.number_input(
            "Target Retirement Age",
            min_value=40,
            max_value=80,
            value=st.session_state.retirement_age,
            help="When you plan to retire",
            key="retirement_age_input"
        )
        st.session_state.retirement_age = retirement_age
        st.info(f"⏰ **Years to Retirement**: {retirement_age - age} years")

        # Life expectancy input with guidance
        with st.expander("📊 **Life Expectancy Guidance**", expanded=False):
            st.markdown("""
            ### 🎯 **How to Estimate Your Life Expectancy**

            **Average Life Expectancy by Age:**
            - **At birth**: ~79 years (US average)
            - **At age 30**: ~80 years
            - **At age 50**: ~82 years
            - **At age 65**: ~85 years

            **Factors to Consider:**
            - **Family history**: Long-lived parents/grandparents
            - **Health status**: Current health conditions
            - **Lifestyle**: Exercise, diet, smoking, stress
            - **Gender**: Women typically live 3-5 years longer
            - **Education/Income**: Higher education/income correlates with longer life

            **Conservative Planning**: Consider adding 5-10 years to your estimate for safety.
            """)

        life_expectancy = st.number_input(
            "Life Expectancy (Age)",
            min_value=retirement_age+1,
            max_value=120,
            value=st.session_state.life_expectancy,
            help="Expected age at death - use guidance above to estimate",
            key="life_expectancy_input"
        )
        st.session_state.life_expectancy = life_expectancy
        years_in_retirement = life_expectancy - retirement_age
        st.info(f"⏳ **Years in Retirement**: {years_in_retirement} years")

    with col2:
        annual_income = st.number_input(
            "Annual Income ($)",
            min_value=10000,
            value=st.session_state.annual_income,
            step=1000,
            help="Your current annual income",
            key="annual_income_input"
        )
        st.session_state.annual_income = annual_income

        # Retirement income goal
        st.subheader("🎯 Retirement Income Goal")
        with st.expander("💡 How to estimate retirement income needs", expanded=False):
            st.markdown("""
            **Common retirement income replacement ratios:**
            - **70-80%**: Conservative estimate (most financial advisors recommend)
            - **60-70%**: Moderate estimate (if you plan to downsize lifestyle)
            - **80-90%**: Higher estimate (if you plan to travel more or have health costs)
            - **100%+**: Same or higher lifestyle in retirement

            **Factors to consider:**
            1. **Lower expenses**: No commuting, work clothes, retirement savings
            2. **Higher expenses**: Healthcare, travel, hobbies
            3. **Social Security**: Will provide some income (check ssa.gov)
            4. **Pension**: If you have one
            5. **Lifestyle changes**: Downsizing, moving to lower-cost area
            """)

        # Calculate suggested retirement income (75% replacement ratio)
        suggested_retirement_income = annual_income * 0.75
        retirement_income_goal = st.number_input(
            "Desired Annual Retirement Income ($)",
            min_value=10000,
            value=st.session_state.retirement_income_goal,
            step=1000,
            help=f"Based on 75% replacement ratio: ${suggested_retirement_income:,.0f}",
            key="retirement_income_goal_input"
        )
        st.session_state.retirement_income_goal = retirement_income_goal

        # Show replacement ratio
        replacement_ratio = (retirement_income_goal / annual_income) * 100
        st.info(f"📊 **Income Replacement Ratio**: {replacement_ratio:.1f}% of current income")

        # Client name for personalization
        client_name = st.text_input(
            "Client Name (for report personalization)",
            value=st.session_state.client_name,
            placeholder="Enter your name for the PDF report",
            help="Optional: Your name will appear on the PDF report",
            key="client_name_input"
        )
        st.session_state.client_name = client_name

    # Navigation button for Step 1
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if st.button("Next: Asset Configuration →", type="primary", use_container_width=True):
            st.session_state.onboarding_step = 2
            st.rerun()

# ==========================================
# STEP 2: Asset Configuration
# ==========================================
elif current_step == 2:
    # Load values from session state for use in this step
    annual_income = st.session_state.annual_income

    # Tax Rate Explanation
    with st.expander("📚 Understanding Tax Rates in Asset Configuration", expanded=False):
        st.markdown("""
        ### 🎯 Tax Rate Column Explained
        
        The **Tax Rate (%)** column specifies the tax rate that applies to **gains only** (not the full balance) for certain account types:
        
        #### **Pre-Tax Accounts (401k, Traditional IRA)**
        - **Tax Rate**: `0%` (not applicable here)
        - **Why**: The entire balance is taxed as ordinary income at withdrawal
        - **Example**: Withdraw $100,000 → pay tax on full amount at retirement tax rate
        
        #### **Post-Tax Accounts**
        **Roth IRA:**
        - **Tax Rate**: `0%` 
        - **Why**: No tax on withdrawals (contributions already taxed)
        - **Example**: Withdraw $100,000 tax-free
        
        **Brokerage Account:**
        - **Tax Rate**: `15%` (default capital gains rate)
        - **Why**: Only the **gains** are taxed, not original contributions
        - **Example**: 
          - Contributed $50,000, grew to $100,000
          - Only $50,000 gain taxed at 15% = $7,500 tax
          - You keep $92,500
        
        #### **Tax-Deferred Accounts (HSA, Annuities)**
        - **Tax Rate**: Varies by account type
        - **HSA**: `0%` for medical expenses, retirement tax rate for other withdrawals
        - **Annuities**: Retirement tax rate on full amount
        
        💡 **Key Insight**: This helps calculate how much you'll actually have available for retirement spending after taxes.
        """)

    # Default Growth Rate Setting
    st.markdown("### 📈 Default Growth Rate for Investment Accounts")
    st.markdown("Set a default growth rate that will auto-populate for your investment accounts.")

    col1, col2 = st.columns([2, 1])
    with col1:
        default_growth_rate = st.slider(
            "Default Annual Growth Rate (%)",
            min_value=0.0,
            max_value=20.0,
            value=7.0,
            step=0.5,
            help="This will be used as the default for stocks/investment accounts. Typical: 7-10% for stocks, 4-5% for bonds, 2-4% for savings"
        )
    with col2:
        st.info(f"**Default Rate:** {default_growth_rate}%")
        st.caption("💡 Typical rates:\n- Stocks: 7-10%\n- Bonds: 4-5%\n- Savings: 2-4%")

    st.markdown("---")

    # Simplified setup options (removed Default Portfolio and Legacy Mode)
    setup_option = st.radio(
        "Choose how to configure your accounts:",
        ["Upload Financial Statements (AI)", "Upload CSV File", "Configure Individual Assets"],
        help="Select how you want to add your retirement accounts"
    )

    assets = []

    if setup_option == "Upload Financial Statements (AI)":
        if not _N8N_AVAILABLE:
            st.error("❌ **n8n integration not available**")
            st.info("Please install required packages: `pip install pypdf python-dotenv requests`")
        else:
            st.info("🤖 **AI-Powered Statement Upload**: Upload your financial PDFs and let AI extract your account data automatically.")

            # Initialize session state for extracted data
            if 'ai_extracted_accounts' not in st.session_state:
                st.session_state.ai_extracted_accounts = None
            if 'ai_tax_buckets' not in st.session_state:
                st.session_state.ai_tax_buckets = {}
            if 'ai_warnings' not in st.session_state:
                st.session_state.ai_warnings = []
            if 'ai_edited_table' not in st.session_state:
                st.session_state.ai_edited_table = None

            # Initialize variables for this run
            df_extracted = None
            tax_buckets_by_account = {}

            # Check if we already have extracted data
            if st.session_state.ai_extracted_accounts is not None:
                st.success(f"✅ Using previously extracted {len(st.session_state.ai_extracted_accounts)} accounts")

                # Add button to clear and re-upload
                if st.button("🔄 Clear and Upload New Statements", type="secondary"):
                    st.session_state.ai_extracted_accounts = None
                    st.session_state.ai_tax_buckets = {}
                    st.session_state.ai_warnings = []
                    st.session_state.ai_edited_table = None
                    st.rerun()

                # Use existing data
                df_extracted = st.session_state.ai_extracted_accounts
                tax_buckets_by_account = st.session_state.ai_tax_buckets
                warnings = st.session_state.ai_warnings

                # Display warnings if any
                if warnings and len(warnings) > 0:
                    with st.expander(f"⚠️ Processing Warnings ({len(warnings)})", expanded=False):
                        for warning in warnings:
                            st.warning(warning)

                # CRITICAL: Convert edited table to assets on every rerun
                # This ensures assets persist even when user changes personal info
                if st.session_state.ai_edited_table is not None:
                    edited_df = st.session_state.ai_edited_table
                    try:
                        assets = []
                        for _, row in edited_df.iterrows():
                            # Parse tax treatment (from human-readable to enum)
                            tax_treatment_str = row["Tax Treatment"]
                            if tax_treatment_str == "Pre-Tax" or tax_treatment_str == "Tax-Deferred":
                                asset_type = AssetType.TAX_DEFERRED
                            elif tax_treatment_str == "Post-Tax":
                                asset_type = AssetType.POST_TAX
                            elif tax_treatment_str == "Tax-Free":
                                # Tax-Free (Roth) maps to POST_TAX with 0% tax rate
                                asset_type = AssetType.POST_TAX
                            else:
                                raise ValueError(f"Invalid tax treatment: {tax_treatment_str}")

                            # Create asset
                            asset = Asset(
                                name=row["Account Name"],
                                asset_type=asset_type,
                                current_balance=float(row["Current Balance"]),
                                annual_contribution=float(row["Annual Contribution"]),
                                growth_rate_pct=float(row["Growth Rate (%)"]),
                                tax_rate_pct=float(row["Tax Rate on Gains (%)"])
                            )
                            assets.append(asset)

                        st.info(f"📊 Using {len(assets)} AI-extracted accounts for retirement analysis")

                    except Exception as e:
                        st.error(f"❌ Error loading AI-extracted accounts: {str(e)}")
                        st.info("💡 Try clicking '🔄 Clear and Upload New Statements' and re-uploading.")

            else:
                # Upload financial statement PDFs
                uploaded_files = st.file_uploader(
                    "📤 Upload Financial Statement PDFs",
                    type=['pdf'],
                    accept_multiple_files=True,
                    help="Upload 401(k), IRA, brokerage, or bank statements"
                )

                if uploaded_files:
                    if st.button("🚀 Extract Account Data", type="primary", use_container_width=True):
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        try:
                            # Initialize n8n client
                            status_text.text("Initializing AI extraction...")
                            progress_bar.progress(10)

                            client = N8NClient()

                            # Prepare files for upload
                            status_text.text(f"Uploading {len(uploaded_files)} file(s)...")
                            progress_bar.progress(30)

                            files_to_upload = [(f.name, f.getvalue()) for f in uploaded_files]

                            # Upload to n8n
                            result = client.upload_statements(files_to_upload)
                            progress_bar.progress(90)

                            if result['success']:
                                progress_bar.progress(100)
                                status_text.text("✓ Extraction complete!")

                                # Parse response (handle both JSON and CSV formats)
                                response_format = result.get('format', 'csv')
                                tax_buckets_by_account = {}

                                if response_format == 'json':
                                    # Split accounts with multiple tax sources BEFORE creating DataFrame
                                    split_accounts = []
                                    for account in result['data']:
                                        # Check if account has multiple non-zero tax sources
                                        raw_tax_sources = account.get('_raw_tax_sources', [])
                                        non_zero_sources = [s for s in raw_tax_sources if s.get('balance', 0) > 0]

                                        if len(non_zero_sources) > 1:
                                            # Split into separate accounts
                                            for source in non_zero_sources:
                                                split_account = account.copy()
                                                source_label = source['label']
                                                source_balance = source['balance']

                                                # Determine tax treatment from source label
                                                if 'roth' in source_label.lower():
                                                    tax_treatment = 'tax_free'
                                                    suffix = '- Roth'
                                                elif 'after tax' in source_label.lower() or 'after-tax' in source_label.lower():
                                                    tax_treatment = 'post_tax'
                                                    suffix = '- After-Tax'
                                                else:  # Employee Deferral, Traditional, etc.
                                                    tax_treatment = 'tax_deferred'
                                                    suffix = '- Traditional'

                                                # Update split account
                                                split_account['account_name'] = f"{account.get('account_name', '401k')} {suffix}"
                                                split_account['ending_balance'] = source_balance
                                                split_account['tax_treatment'] = tax_treatment
                                                split_account['_tax_source_label'] = source_label
                                                # Remove _raw_tax_sources to avoid confusion
                                                split_account.pop('_raw_tax_sources', None)

                                                split_accounts.append(split_account)
                                        else:
                                            # Keep account as-is
                                            split_accounts.append(account)

                                    # Save tax_buckets or raw_tax_sources before converting to DataFrame
                                    for idx, account in enumerate(split_accounts):
                                        account_id = account.get('account_id') or account.get('account_name') or f"account_{idx}"

                                        # Check for processed tax_buckets first
                                        if 'tax_buckets' in account and account['tax_buckets']:
                                            tax_buckets_by_account[account_id] = account['tax_buckets']
                                        # Fall back to raw_tax_sources if available
                                        elif '_raw_tax_sources' in account and account['_raw_tax_sources']:
                                            # Convert raw_tax_sources to bucket format for display
                                            raw_sources = account['_raw_tax_sources']
                                            buckets = []
                                            for source in raw_sources:
                                                if source.get('balance', 0) > 0:  # Only show non-zero balances
                                                    # Map label to tax treatment
                                                    label = source['label'].lower()
                                                    if 'roth' in label:
                                                        tax_treatment_bucket = 'tax_free'
                                                    elif 'after tax' in label or 'after-tax' in label:
                                                        tax_treatment_bucket = 'post_tax'
                                                    else:  # Employee deferral, traditional, etc.
                                                        tax_treatment_bucket = 'tax_deferred'

                                                    buckets.append({
                                                        'bucket_type': source['label'],
                                                        'tax_treatment': tax_treatment_bucket,
                                                        'balance': source['balance']
                                                    })
                                            if buckets:
                                                tax_buckets_by_account[account_id] = buckets

                                    # JSON format - already a list of dicts
                                    df_extracted = pd.DataFrame(split_accounts)
                                    # Rename JSON fields if needed
                                    column_mapping = {
                                        'account_name': 'label',
                                        'ending_balance': 'value',
                                        'balance_as_of_date': 'period_end',
                                        'institution': 'document_type',
                                        'account_id': 'account_id'
                                    }
                                    df_extracted = df_extracted.rename(columns={k: v for k, v in column_mapping.items() if k in df_extracted.columns})
                                else:
                                    # CSV format
                                    csv_content = result['data']
                                    df_extracted = pd.read_csv(io.StringIO(csv_content))

                                # Convert to numeric
                                if 'value' in df_extracted.columns:
                                    df_extracted['value'] = pd.to_numeric(df_extracted['value'], errors='coerce')
                                elif 'ending_balance' in df_extracted.columns:
                                    df_extracted['value'] = pd.to_numeric(df_extracted['ending_balance'], errors='coerce')

                                # Store in session state for persistence across reruns
                                st.session_state.ai_extracted_accounts = df_extracted
                                st.session_state.ai_tax_buckets = tax_buckets_by_account
                                st.session_state.ai_warnings = result.get('warnings', [])

                                st.success(f"✅ Extracted {len(df_extracted)} accounts from your statements!")
                                st.info("💡 **Data saved!** You can now edit other fields without losing your extracted accounts.")

                                # Display warnings if any
                                warnings = st.session_state.ai_warnings
                                if warnings and len(warnings) > 0:
                                    with st.expander(f"⚠️ Processing Warnings ({len(warnings)})", expanded=False):
                                        for warning in warnings:
                                            st.warning(warning)

                                # Map extracted data to Asset objects
                                with st.expander("📋 Extracted Accounts (Editable)", expanded=True):
                                    st.info("💡 **Review and edit the extracted data below. Add estimated annual contributions and expected growth rates.**")

                                    # Helper function to humanize account type
                                    def humanize_account_type(account_type: str) -> str:
                                        """Convert account_type codes to human-readable format."""
                                        if not account_type:
                                            return 'Unknown'

                                        mappings = {
                                            '401k': '401(k)',
                                            'ira': 'IRA',
                                            'roth_ira': 'Roth IRA',
                                            'traditional_ira': 'Traditional IRA',
                                            'rollover_ira': 'Rollover IRA',
                                            'savings': 'Savings Account',
                                            'checking': 'Checking Account',
                                            'brokerage': 'Brokerage Account',
                                            'hsa': 'HSA (Health Savings Account)',
                                            'high yield savings': 'High Yield Savings',
                                            'stock_plan': 'Stock Plan',
                                            'roth': 'Roth IRA',
                                            '403b': '403(b)',
                                            '457': '457 Plan'
                                        }
                                        account_type_lower = str(account_type).lower().strip()

                                        # Check exact match first
                                        if account_type_lower in mappings:
                                            return mappings[account_type_lower]

                                        # Check if it contains key patterns
                                        for key, value in mappings.items():
                                            if key in account_type_lower:
                                                return value

                                        # Default: title case with underscores removed
                                        return account_type.replace('_', ' ').title()

                                    # Check if we already have edited table data in session state
                                    if st.session_state.ai_edited_table is not None:
                                        # Use previously edited table
                                        df_table = st.session_state.ai_edited_table
                                    else:
                                        # Create editable table from extracted data (first time)
                                        table_data = []
                                        for idx, row in df_extracted.iterrows():
                                            # Get account type first (we'll need it for inference)
                                            account_type_raw = row.get('account_type', '')
                                            account_type = humanize_account_type(account_type_raw)

                                            # Map tax_treatment to AssetType (human-readable)
                                            # If tax_treatment is missing, infer from account_type
                                            tax_treatment = str(row.get('tax_treatment', '')).lower()
    
                                            if not tax_treatment or tax_treatment == 'nan':
                                                # Infer from account_type
                                                account_type_lower = str(account_type_raw).lower()
                                                if account_type_lower in ['401k', '403b', '457', 'ira', 'traditional_ira']:
                                                    tax_treatment = 'tax_deferred'
                                                elif account_type_lower in ['roth_401k', 'roth_ira', 'roth_403b']:
                                                    tax_treatment = 'tax_free'
                                                elif account_type_lower == 'hsa':
                                                    tax_treatment = 'tax_deferred'  # HSA is tax-deferred
                                                else:
                                                    tax_treatment = 'post_tax'  # brokerage, savings, checking
    
                                            # Map to display value
                                            if tax_treatment == 'pre_tax' or tax_treatment == 'tax_deferred':
                                                asset_type_display = 'Tax-Deferred'
                                            elif tax_treatment == 'post_tax':
                                                asset_type_display = 'Post-Tax'
                                            elif tax_treatment == 'tax_free':
                                                asset_type_display = 'Tax-Free'
                                            else:
                                                asset_type_display = 'Post-Tax'  # default
    
                                            # Get account name and humanize it
                                            account_name_raw = str(row.get('label', f"Account {idx+1}"))
    
                                            # Helper function to humanize account names
                                            def humanize_account_name(name: str) -> str:
                                                """Convert raw account names to human-readable format."""
                                                # Handle common patterns
                                                name_clean = name.strip()
    
                                                # Stock plans - extract company and plan type
                                                if 'STOCK PLAN' in name_clean.upper():
                                                    # "STOCK PLAN - MICROSOFT ESPP PLAN" → "Microsoft ESPP"
                                                    # "STOCK PLAN - ORACLE STOCK OPTIONS" → "Oracle Stock Options"
                                                    parts = name_clean.split('-')
                                                    if len(parts) >= 2:
                                                        plan_details = parts[1].strip()
                                                        # Extract company name (first word) and plan type
                                                        words = plan_details.split()
                                                        if len(words) >= 2:
                                                            company = words[0].title()
                                                            if 'ESPP' in plan_details.upper():
                                                                return f"{company} ESPP"
                                                            elif 'STOCK OPTION' in plan_details.upper():
                                                                return f"{company} Stock Options"
                                                            elif 'RSU' in plan_details.upper():
                                                                return f"{company} RSUs"
                                                            else:
                                                                plan_type = ' '.join(words[1:]).title()
                                                                return f"{company} {plan_type}"
    
                                                # Brokerage accounts
                                                if 'at Work Self-Directed' in name_clean:
                                                    # "Morgan Stanley at Work Self-Directed Account" → "Morgan Stanley Brokerage"
                                                    institution = name_clean.split(' at Work')[0]
                                                    return f"{institution} Brokerage"
    
                                                # Generic brokerage account shortening
                                                if name_clean.lower() == 'brokerage account':
                                                    return 'Brokerage'
    
                                                # Fix common formatting issues
                                                replacements = {
                                                    'rollover_ira': 'Rollover IRA',
                                                    'roth_ira': 'Roth IRA',
                                                    'traditional_ira': 'Traditional IRA',
                                                    'health_savings_account': 'HSA',
                                                    '401k': '401(k)',
                                                    '403b': '403(b)',
                                                    '457': '457(b)',
                                                }
    
                                                name_lower = name_clean.lower()
                                                for key, value in replacements.items():
                                                    if key == name_lower:
                                                        return value
                                                    # Also handle patterns like "401k - Traditional"
                                                    if name_lower.startswith(key):
                                                        suffix = name_clean[len(key):].strip()
                                                        return f"{value}{suffix}"
    
                                                # Title case for all-caps names
                                                if name_clean.isupper():
                                                    return name_clean.title()
    
                                                # Return as-is if no pattern matches
                                                return name_clean
    
                                            account_name = humanize_account_name(account_name_raw)
    
                                            # Get institution and account number for display
                                            institution = str(row.get('document_type', ''))  # Institution is stored in document_type
                                            account_number_last4 = str(row.get('account_number_last4', '')) if pd.notna(row.get('account_number_last4')) else ''
    
                                            # Get current balance
                                            current_balance = float(row.get('value', 0))
    
                                            # Helper function to humanize income eligibility
                                            def humanize_eligibility(value: str) -> str:
                                                mappings = {
                                                    'eligible': '✅ Eligible',
                                                    'conditionally_eligible': '⚠️ Conditionally Eligible',
                                                    'not_eligible': '❌ Not Eligible'
                                                }
                                                return mappings.get(str(value).lower(), value)
    
                                            # Helper function to humanize purpose
                                            def humanize_purpose(value: str) -> str:
                                                mappings = {
                                                    'income': 'Retirement Income',
                                                    'general_income': 'General Income',
                                                    'healthcare_only': 'Healthcare Only (HSA)',
                                                    'education_only': 'Education Only (529)',
                                                    'employment_compensation': 'Employment Compensation',
                                                    'restricted_other': 'Restricted/Other'
                                                }
                                                return mappings.get(str(value).lower(), value)
    
                                            # Get income eligibility and purpose if available
                                            income_eligibility = row.get('income_eligibility', '')
                                            purpose = row.get('purpose', '')
    
                                            # Set default tax rate based on tax treatment
                                            if asset_type_display == 'Post-Tax':
                                                default_tax_rate = 15.0  # Capital gains tax
                                            else:
                                                default_tax_rate = 0.0  # Tax-Deferred and Tax-Free both show 0% here
    
                                            # Set default growth rate based on account type
                                            account_type_lower = str(account_type_raw).lower()
                                            if account_type_lower in ['savings', 'checking']:
                                                account_growth_rate = 3.0  # HYSA/Savings: conservative rate
                                            else:
                                                # Use the user's default growth rate for all investment accounts
                                                account_growth_rate = default_growth_rate
    
                                            table_row = {
                                                "#": f"#{idx+1}",
                                                "Institution": institution,
                                                "Account Name": account_name,
                                                "Last 4": account_number_last4,
                                                "Account Type": account_type,
                                                "Tax Treatment": asset_type_display,
                                                "Current Balance": current_balance,
                                                "Annual Contribution": 0.0,  # User needs to fill
                                                "Growth Rate (%)": account_growth_rate,
                                                "Tax Rate on Gains (%)": default_tax_rate
                                            }
    
                                            # Add income eligibility if available
                                            if income_eligibility:
                                                table_row["Income Eligibility"] = humanize_eligibility(income_eligibility)
    
                                            # Add purpose if available
                                            if purpose:
                                                table_row["Purpose"] = humanize_purpose(purpose)
    
                                            table_data.append(table_row)

                                        # Create DataFrame from table_data
                                        df_table = pd.DataFrame(table_data)

                                    # Define column configuration
                                    column_config = {
                                        "#": st.column_config.TextColumn("#", disabled=True, help="Row number", width="small"),
                                        "Institution": st.column_config.TextColumn(
                                            "Institution",
                                            disabled=True,
                                            help="Financial institution (e.g., Fidelity, Morgan Stanley)",
                                            width="medium"
                                        ),
                                        "Account Name": st.column_config.TextColumn(
                                            "Account Name",
                                            help="Account name/description from statement",
                                            width="medium"
                                        ),
                                        "Last 4": st.column_config.TextColumn(
                                            "Last 4",
                                            disabled=True,
                                            help="Last 4 digits of account number",
                                            width="small"
                                        ),
                                        "Account Type": st.column_config.TextColumn(
                                            "Account Type",
                                            disabled=True,
                                            help="Type of account (401k, IRA, Savings, etc.) - extracted from statement",
                                            width="small"
                                        ),
                                        "Tax Treatment": st.column_config.SelectboxColumn(
                                            "Tax Treatment",
                                            options=["Tax-Deferred", "Tax-Free", "Post-Tax"],
                                            help="Tax treatment: Tax-Deferred (401k/IRA), Tax-Free (Roth IRA/Roth 401k), Post-Tax (Brokerage/Savings)"
                                        ),
                                        "Current Balance": st.column_config.NumberColumn(
                                            "Current Balance ($)",
                                            min_value=0,
                                            format="$%d",
                                            help="Current account balance (extracted from statements)"
                                        ),
                                        "Annual Contribution": st.column_config.NumberColumn(
                                            "Annual Contribution ($)",
                                            min_value=0,
                                            format="$%d",
                                            help="How much you contribute annually to this account"
                                        ),
                                        "Growth Rate (%)": st.column_config.NumberColumn(
                                            "Growth Rate (%)",
                                            min_value=0,
                                            max_value=50,
                                            format="%.1f%%",
                                            help=f"Expected annual growth rate (your default: {default_growth_rate}%)"
                                        ),
                                        "Tax Rate on Gains (%)": st.column_config.NumberColumn(
                                            "Tax Rate on Gains (%)",
                                            min_value=0,
                                            max_value=50,
                                            format="%.1f%%",
                                            help="Tax rate on GAINS only: 0% for Roth/Tax-Deferred, 15% for brokerage capital gains"
                                        ),
                                        "Income Eligibility": st.column_config.TextColumn(
                                            "Income Eligibility",
                                            disabled=True,
                                            help="Can this account be used for retirement income? ✅ Eligible, ⚠️ Conditionally Eligible, ❌ Not Eligible"
                                        ),
                                        "Purpose": st.column_config.TextColumn(
                                            "Purpose",
                                            disabled=True,
                                            help="Primary purpose of this account (e.g., Retirement Income, Healthcare, Education)"
                                        )
                                    }

                                    # Display editable table
                                    edited_df = st.data_editor(
                                        df_table,
                                        column_config=column_config,
                                        use_container_width=True,
                                        hide_index=True,
                                        num_rows="dynamic"
                                    )

                                    # Save edited table to session state for persistence across reruns
                                    st.session_state.ai_edited_table = edited_df

                                    # Display tax bucket breakdowns if available
                                    if tax_buckets_by_account:
                                        st.markdown("---")
                                        st.markdown("#### 🔍 Tax Bucket Breakdown")
                                        st.info("**Detailed tax source breakdown for retirement accounts with multiple tax treatments**")

                                        for account_id, buckets in tax_buckets_by_account.items():
                                            # Find account name in DataFrame
                                            account_row = df_extracted[df_extracted.get('account_id') == account_id] if 'account_id' in df_extracted.columns else None
                                            if account_row is not None and not account_row.empty:
                                                account_name = account_row.iloc[0].get('label', account_id)
                                            else:
                                                account_name = account_id

                                            with st.expander(f"📊 {account_name}"):
                                                # Create DataFrame for buckets
                                                bucket_df = pd.DataFrame(buckets)

                                                # Humanize bucket_type and tax_treatment
                                                def humanize_bucket(value: str) -> str:
                                                    mappings = {
                                                        'traditional_401k': 'Traditional 401(k)',
                                                        'roth_in_plan_conversion': 'Roth In-Plan Conversion',
                                                        'after_tax_401k': 'After-Tax 401(k)',
                                                        'tax_deferred': 'Tax-Deferred',
                                                        'tax_free': 'Tax-Free',
                                                        'post_tax': 'Post-Tax',
                                                        'pre_tax': 'Pre-Tax'
                                                    }
                                                    return mappings.get(str(value).lower(), value)

                                                if 'bucket_type' in bucket_df.columns:
                                                    bucket_df['bucket_type'] = bucket_df['bucket_type'].apply(humanize_bucket)
                                                if 'tax_treatment' in bucket_df.columns:
                                                    bucket_df['tax_treatment'] = bucket_df['tax_treatment'].apply(humanize_bucket)

                                                # Format balance as currency
                                                if 'balance' in bucket_df.columns:
                                                    total_bucket_balance = bucket_df['balance'].sum()
                                                    bucket_df['balance'] = bucket_df['balance'].apply(lambda x: f"${x:,.2f}")

                                                # Rename columns
                                                bucket_df = bucket_df.rename(columns={
                                                    'bucket_type': 'Tax Bucket',
                                                    'tax_treatment': 'Tax Treatment',
                                                    'balance': 'Balance'
                                                })

                                                st.dataframe(bucket_df, use_container_width=True, hide_index=True)

                                                # Show total
                                                st.metric("Total", f"${total_bucket_balance:,.2f}")

                                    # Convert edited dataframe to Asset objects
                                    if not edited_df.empty:
                                        try:
                                            assets = []
                                            for _, row in edited_df.iterrows():
                                                # Parse tax treatment (from human-readable to enum)
                                                tax_treatment_str = row["Tax Treatment"]
                                                if tax_treatment_str == "Pre-Tax" or tax_treatment_str == "Tax-Deferred":
                                                    asset_type = AssetType.TAX_DEFERRED
                                                elif tax_treatment_str == "Post-Tax":
                                                    asset_type = AssetType.POST_TAX
                                                elif tax_treatment_str == "Tax-Free":
                                                    # Tax-Free (Roth) maps to POST_TAX with 0% tax rate
                                                    asset_type = AssetType.POST_TAX
                                                else:
                                                    raise ValueError(f"Invalid tax treatment: {tax_treatment_str}")

                                                # Create asset
                                                asset = Asset(
                                                    name=row["Account Name"],
                                                    asset_type=asset_type,
                                                    current_balance=float(row["Current Balance"]),
                                                    annual_contribution=float(row["Annual Contribution"]),
                                                    growth_rate_pct=float(row["Growth Rate (%)"]),
                                                    tax_rate_pct=float(row["Tax Rate on Gains (%)"])
                                                )
                                                assets.append(asset)

                                            st.success(f"✅ {len(assets)} accounts ready for retirement analysis!")

                                        except Exception as e:
                                            st.error(f"❌ Error processing extracted data: {str(e)}")
                                            st.info("💡 Please check the values in the table.")

                            else:
                                progress_bar.progress(100)
                                status_text.text("✗ Extraction failed")
                                st.error(f"Extraction Error: {result.get('error', 'Unknown error')}")

                        except N8NError as e:
                            progress_bar.progress(100)
                            status_text.text("✗ Configuration error")
                            st.error(f"Configuration Error: {str(e)}")
                            st.info("💡 Make sure your .env file has the N8N_WEBHOOK_URL configured.")

                        except Exception as e:
                            progress_bar.progress(100)
                            status_text.text("✗ Unexpected error")
                            st.error(f"Error: {str(e)}")

    elif setup_option == "Upload CSV File":
        st.info("📁 **CSV Upload Method**: Download a template, modify it with your data, then upload it back.")
        
        # Download template button
        csv_template = create_asset_template_csv()
        st.download_button(
            label="📥 Download CSV Template",
            data=csv_template,
            file_name="asset_template.csv",
            mime="text/csv",
            help="Download a pre-filled template with example data"
        )
        
        # Upload file
        uploaded_file = st.file_uploader(
            "📤 Upload Your CSV File",
            type=['csv'],
            help="Upload your modified CSV file with your asset data"
        )
        
        if uploaded_file is not None:
            try:
                # Read uploaded file
                csv_content = uploaded_file.read().decode('utf-8')
                assets = parse_uploaded_csv(csv_content)
                
                st.success(f"✅ Successfully loaded {len(assets)} assets from CSV file!")
                
                # Show uploaded assets in editable table format
                with st.expander("📋 Uploaded Assets (Editable)", expanded=True):
                    # Helper function to convert asset type to human-readable format
                    def asset_type_to_display(asset: Asset) -> str:
                        """Convert AssetType enum to human-readable display value."""
                        if asset.asset_type == AssetType.PRE_TAX or asset.asset_type == AssetType.TAX_DEFERRED:
                            return "Tax-Deferred"
                        elif asset.asset_type == AssetType.POST_TAX:
                            # Check tax rate to distinguish Roth (Tax-Free) from Brokerage (Post-Tax)
                            if asset.tax_rate_pct == 0:
                                return "Tax-Free"
                            else:
                                return "Post-Tax"
                        return "Post-Tax"  # default

                    # Create editable table data
                    table_data = []
                    for i, asset in enumerate(assets):
                        row = {
                            "Index": i,
                            "Account Name": asset.name,
                            "Tax Treatment": asset_type_to_display(asset),
                            "Current Balance": asset.current_balance,
                            "Annual Contribution": asset.annual_contribution,
                            "Growth Rate (%)": asset.growth_rate_pct,
                            "Tax Rate on Gains (%)": asset.tax_rate_pct
                        }
                        table_data.append(row)
                    
                    # Create editable dataframe
                    df = pd.DataFrame(table_data)
                    
                    # Define column configuration for editing
                    column_config = {
                        "Index": st.column_config.NumberColumn("Index", disabled=True, help="Asset index (read-only)"),
                        "Account Name": st.column_config.TextColumn("Account Name", help="Name of the account"),
                        "Tax Treatment": st.column_config.SelectboxColumn(
                            "Tax Treatment",
                            options=["Tax-Deferred", "Tax-Free", "Post-Tax"],
                            help="Tax treatment: Tax-Deferred (401k/Traditional IRA), Tax-Free (Roth IRA/Roth 401k), Post-Tax (Brokerage/Savings)"
                        ),
                        "Current Balance": st.column_config.NumberColumn(
                            "Current Balance ($)",
                            min_value=0,
                            format="$%d",
                            help="Current account balance"
                        ),
                        "Annual Contribution": st.column_config.NumberColumn(
                            "Annual Contribution ($)",
                            min_value=0,
                            format="$%d",
                            help="Annual contribution amount"
                        ),
                        "Growth Rate (%)": st.column_config.NumberColumn(
                            "Growth Rate (%)",
                            min_value=0,
                            max_value=50,
                            format="%.1f%%",
                            help=f"Expected annual growth rate (your default: {default_growth_rate}%)"
                        ),
                        "Tax Rate on Gains (%)": st.column_config.NumberColumn(
                            "Tax Rate on Gains (%)",
                            min_value=0,
                            max_value=50,
                            format="%.1f%%",
                            help="Tax rate on GAINS only: 0% for Roth/Tax-Deferred, 15% for brokerage capital gains"
                        )
                    }
                    
                    # Display editable table
                    st.info("💡 **Edit your assets directly in the table below. Changes will be applied when you run the analysis.**")
                    edited_df = st.data_editor(
                        df, 
                        column_config=column_config,
                        use_container_width=True, 
                        hide_index=True,
                        num_rows="dynamic"
                    )
                    
                    # Convert edited dataframe back to Asset objects
                    if not edited_df.empty:
                        try:
                            updated_assets = []
                            for _, row in edited_df.iterrows():
                                # Parse tax treatment (from human-readable to enum)
                                tax_treatment_str = row["Tax Treatment"]
                                if tax_treatment_str == "Tax-Deferred":
                                    asset_type = AssetType.TAX_DEFERRED
                                elif tax_treatment_str == "Post-Tax":
                                    asset_type = AssetType.POST_TAX
                                elif tax_treatment_str == "Tax-Free":
                                    # Tax-Free (Roth) maps to POST_TAX with 0% tax rate
                                    asset_type = AssetType.POST_TAX
                                else:
                                    raise ValueError(f"Invalid tax treatment: {tax_treatment_str}")

                                # Create updated asset
                                updated_asset = Asset(
                                    name=row["Account Name"],
                                    asset_type=asset_type,
                                    current_balance=float(row["Current Balance"]),
                                    annual_contribution=float(row["Annual Contribution"]),
                                    growth_rate_pct=float(row["Growth Rate (%)"]),
                                    tax_rate_pct=float(row["Tax Rate on Gains (%)"])
                                )
                                updated_assets.append(updated_asset)
                            
                            # Update the assets list
                            assets = updated_assets
                            st.success(f"✅ Assets updated! {len(assets)} assets ready for analysis.")
                            
                        except Exception as e:
                            st.error(f"❌ Error updating assets: {str(e)}")
                            st.info("💡 Please check your input values and try again.")
                
            except Exception as e:
                st.error(f"❌ Error processing CSV file: {str(e)}")
                st.info("💡 **Tip**: Make sure your CSV has the correct format. Download the template and use it as a guide.")
        
    elif setup_option == "Configure Individual Assets":
        st.info("🔧 **Manual Configuration**: Add each asset one by one using the form below.")
        
        num_assets = st.number_input("Number of Assets", min_value=1, max_value=10, value=3, help="How many different accounts do you have?")
        
        for i in range(num_assets):
            with st.expander(f"🏦 Asset {i+1}", expanded=(i==0)):
                col1, col2, col3 = st.columns(3)
                with col1:
                    asset_name = st.text_input(f"Asset Name {i+1}", value=f"Asset {i+1}", help="Name of your account")
                    asset_type = st.selectbox(
                        f"Asset Type {i+1}",
                        options=[(name, atype) for name, atype in _DEF_ASSET_TYPES],
                        format_func=lambda x: f"{x[0]} ({x[1].value})",
                        help="Type of account for tax treatment"
                    )
                with col2:
                    current_balance = st.number_input(f"Current Balance {i+1} ($)", min_value=0, value=10000, step=1000, help="Current account balance")
                    annual_contribution = st.number_input(f"Annual Contribution {i+1} ($)", min_value=0, value=5000, step=500, help="How much you contribute annually")
                with col3:
                    growth_rate = st.slider(f"Growth Rate {i+1} (%)", 0, 20, int(default_growth_rate), help=f"Expected annual return (default: {default_growth_rate}%)")
                    if asset_type[1] == AssetType.POST_TAX and "Brokerage" in asset_name:
                        tax_rate = st.slider(f"Capital Gains Rate {i+1} (%)", 0, 30, 15, help="Capital gains tax rate")
                    else:
                        tax_rate = 0
                
                assets.append(Asset(
                    name=asset_name,
                    asset_type=asset_type[1],
                    current_balance=current_balance,
                    annual_contribution=annual_contribution,
                    growth_rate_pct=growth_rate,
                    tax_rate_pct=tax_rate
                ))

    # Save assets to session state
    st.session_state.assets = assets

    # Navigation buttons for Step 2
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← Previous: Personal Info", use_container_width=True):
            st.session_state.onboarding_step = 1
            st.rerun()
    with col3:
        if st.button("Complete Onboarding ✓", type="primary", use_container_width=True):
            st.session_state.onboarding_complete = True
            st.session_state.onboarding_step = 2  # Stay on step 2
            st.rerun()

# ==========================================
# Results Section
# ==========================================
# Only show results after onboarding is complete
if not st.session_state.onboarding_complete:
    st.markdown("---")
    st.info("👆 **Please complete the onboarding steps above to see your retirement projection results.**")
    st.stop()

# Results Section with clear visual separation
st.markdown("---")
st.header("📊 Retirement Projection Results")

# Calculate values from session state for results
current_year = datetime.now().year
age = current_year - st.session_state.birth_year
retirement_age = st.session_state.retirement_age
life_expectancy = st.session_state.life_expectancy
annual_income = st.session_state.annual_income
retirement_income_goal = st.session_state.retirement_income_goal
client_name = st.session_state.client_name
assets = st.session_state.assets

try:
    inputs = UserInputs(
        age=int(age),
        retirement_age=int(retirement_age),
        life_expectancy=int(life_expectancy),
        annual_income=float(annual_income),
        contribution_rate_pct=15.0,  # Not used in new system
        expected_growth_rate_pct=7.0,  # Not used in new system
        inflation_rate_pct=float(inflation_rate),
        current_marginal_tax_rate_pct=float(current_tax_rate),
        retirement_marginal_tax_rate_pct=float(retirement_tax_rate),
        assets=assets
    )

    result = project(inputs)

    # Key metrics in a prominent container
    with st.container():
        st.subheader("🎯 Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Years to Retirement", f"{result['Years Until Retirement']:.0f}")
        with col2:
            st.metric("Total Pre-Tax Value", f"${result['Total Future Value (Pre-Tax)']:,.0f}")
        with col3:
            st.metric("Total After-Tax Value", f"${result['Total After-Tax Balance']:,.0f}")
        with col4:
            st.metric("Tax Efficiency", f"{result['Tax Efficiency (%)']:.1f}%")
    
    # Income Analysis Section
    st.markdown("---")
    st.subheader("💰 Retirement Income Analysis")
    
    # Calculate retirement income from portfolio
    total_after_tax = result['Total After-Tax Balance']
    years_in_retirement = life_expectancy - retirement_age  # Use actual life expectancy
    annual_retirement_income = total_after_tax / years_in_retirement
    
    # Calculate shortfall or surplus
    income_shortfall = retirement_income_goal - annual_retirement_income
    income_ratio = (annual_retirement_income / retirement_income_goal) * 100
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Projected Annual Income", 
            f"${annual_retirement_income:,.0f}",
            help=f"Based on {years_in_retirement}-year retirement period (age {retirement_age} to {life_expectancy})"
        )
    with col2:
        st.metric(
            "Income Goal", 
            f"${retirement_income_goal:,.0f}",
            help="Your desired retirement income"
        )
    with col3:
        if income_shortfall > 0:
            st.metric(
                "Annual Shortfall", 
                f"${income_shortfall:,.0f}",
                delta=f"-{income_ratio:.1f}%",
                delta_color="inverse"
            )
        else:
            surplus = -income_shortfall
            st.metric(
                "Annual Surplus", 
                f"${surplus:,.0f}",
                delta=f"+{income_ratio:.1f}%",
                delta_color="normal"
            )
    
    # Income status analysis
    if income_ratio >= 100:
        st.success(f"🎉 **Excellent!** You're projected to exceed your retirement income goal by {income_ratio-100:.1f}%!")
    elif income_ratio >= 80:
        st.warning(f"⚠️ **Good progress!** You're on track for {income_ratio:.1f}% of your retirement income goal.")
    elif income_ratio >= 60:
        st.warning(f"🚨 **Needs attention!** You're only projected to achieve {income_ratio:.1f}% of your retirement income goal.")
    else:
        st.error(f"❌ **Significant shortfall!** You're only projected to achieve {income_ratio:.1f}% of your retirement income goal.")
    
    # Recommendations based on income analysis
    with st.expander("💡 Income Optimization Recommendations", expanded=False):
        if income_shortfall > 0:
            st.markdown(f"""
            **To close the ${income_shortfall:,.0f} annual shortfall:**
            
            1. **Increase contributions**: Boost annual savings by ${income_shortfall * 0.1:,.0f} per year
            2. **Extend retirement age**: Work {income_shortfall / (annual_retirement_income * 0.05):.1f} additional years
            3. **Optimize asset allocation**: Consider higher-growth investments
            4. **Reduce retirement expenses**: Lower your income goal by ${income_shortfall * 0.2:,.0f}
            5. **Consider part-time work**: Supplement retirement income
            """)
        else:
            st.markdown("""
            **You're on track! Consider these optimizations:**
            
            1. **Tax optimization**: Maximize Roth contributions
            2. **Asset allocation**: Balance growth vs. preservation
            3. **Estate planning**: Consider legacy goals
            4. **Lifestyle upgrades**: You may be able to increase retirement spending
            """)
    
    # Detailed breakdown in tabs
    st.subheader("📈 Detailed Analysis")
    
    detail_tab1, detail_tab2, detail_tab3 = st.tabs(["💰 Portfolio Breakdown", "📊 Tax Analysis", "📋 Summary"])
    
    with detail_tab1:
        st.write("**Individual Asset Values at Retirement**")

        # Helper function to humanize account names
        def humanize_account_name(name: str) -> str:
            """Convert account names to human-readable format."""
            replacements = {
                'roth_ira': 'Roth IRA',
                'ira': 'IRA',
                '401k': '401(k)',
                'hsa': 'HSA (Health Savings Account)'
            }
            name_lower = name.lower()
            for key, value in replacements.items():
                if name_lower == key:
                    return value
            return name  # Return original if no match

        # Create detailed asset breakdown with calculation explainability
        if 'asset_results' in result and 'assets_input' in result:
            asset_data = []
            # Track totals for summary row
            total_current = 0
            total_contributions = 0
            total_growth = 0
            total_pre_tax = 0
            total_taxes = 0
            total_after_tax = 0

            for i, (asset_result, asset_input) in enumerate(zip(result['asset_results'], result['assets_input'])):
                current_balance = asset_input.current_balance
                contributions = asset_result['total_contributions']
                pre_tax_value = asset_result['pre_tax_value']
                tax_liability = asset_result['tax_liability']
                after_tax_value = asset_result['after_tax_value']

                # Calculate investment growth
                growth = pre_tax_value - current_balance - contributions

                # Accumulate totals
                total_current += current_balance
                total_contributions += contributions
                total_growth += growth
                total_pre_tax += pre_tax_value
                total_taxes += tax_liability
                total_after_tax += after_tax_value

                asset_data.append({
                    "Account": humanize_account_name(asset_result['name']),
                    "Current Balance": f"${current_balance:,.0f}",
                    "Your Contributions": f"${contributions:,.0f}",
                    "Investment Growth": f"${growth:,.0f}",
                    "Pre-Tax Value": f"${pre_tax_value:,.0f}",
                    "Est. Taxes": f"${tax_liability:,.0f}",
                    "After-Tax Value": f"${after_tax_value:,.0f}"
                })

            # Add totals row
            if asset_data:
                asset_data.append({
                    "Account": "📊 TOTAL",
                    "Current Balance": f"${total_current:,.0f}",
                    "Your Contributions": f"${total_contributions:,.0f}",
                    "Investment Growth": f"${total_growth:,.0f}",
                    "Pre-Tax Value": f"${total_pre_tax:,.0f}",
                    "Est. Taxes": f"${total_taxes:,.0f}",
                    "After-Tax Value": f"${total_after_tax:,.0f}"
                })

            if asset_data:
                st.info("💡 **How to read this table**: Current Balance → Add Your Contributions → Add Investment Growth = Pre-Tax Value → Subtract Taxes = After-Tax Value")
                st.dataframe(pd.DataFrame(asset_data), use_container_width=True, hide_index=True)
            else:
                st.info("No individual asset breakdown available")
        else:
            # Fallback to old format if detailed data not available
            asset_data = []
            for key, value in result.items():
                if "Asset" in key and "After-Tax" in key:
                    asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
                    asset_data.append({
                        "Account": humanize_account_name(asset_name),
                        "After-Tax Value": f"${value:,.0f}"
                    })

            if asset_data:
                st.dataframe(pd.DataFrame(asset_data), use_container_width=True, hide_index=True)
            else:
                st.info("No individual asset breakdown available")
    
    with detail_tab2:
        tax_liability = result.get("Total Tax Liability", 0)
        total_pre_tax = result.get("Total Future Value (Pre-Tax)", 1)
        tax_percentage = (tax_liability / total_pre_tax * 100) if total_pre_tax > 0 else 0
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Tax Liability", f"${tax_liability:,.0f}")
            st.metric("Tax as % of Pre-Tax Value", f"{tax_percentage:.1f}%")
        
        with col2:
            if result["Tax Efficiency (%)"] > 85:
                st.success("🎉 **Excellent tax efficiency!** Your portfolio is well-optimized with minimal tax liability.")
            elif result["Tax Efficiency (%)"] > 75:
                st.warning(f"⚠️ **Good tax efficiency** ({tax_percentage:.1f}% tax burden), but there may be room for improvement. *Goal: Lower this percentage by shifting assets to tax-advantaged accounts.*")
                with st.expander("💡 **Get Tax Optimization Advice**", expanded=False):
                    st.markdown("""
                    ### 🎯 **Tax Optimization Strategies**
                    
                    **1. Asset Location Optimization:**
                    - **Taxable accounts**: Hold tax-efficient index funds, municipal bonds
                    - **401(k)/IRA**: Hold high-dividend stocks, REITs, bonds
                    - **Roth IRA**: Hold high-growth stocks, international funds
                    
                    **2. Contribution Strategy:**
                    - **Maximize employer 401(k) match** (free money!)
                    - **Consider Roth vs Traditional** based on current vs future tax rates
                    - **Backdoor Roth IRA** if income exceeds limits
                    
                    **3. Withdrawal Strategy:**
                    - **Tax-loss harvesting** in taxable accounts
                    - **Roth conversion** during low-income years
                    - **Strategic withdrawal order**: Taxable → Traditional → Roth
                    
                    **4. Advanced Strategies:**
                    - **HSA triple tax advantage** for medical expenses
                    - **Municipal bonds** for high tax brackets
                    - **Tax-efficient fund selection** (low turnover, index funds)
                    
                    💡 **Next Steps**: Consider consulting a tax professional for personalized advice based on your specific situation.
                    """)
            else:
                st.error("🚨 **Consider tax optimization** strategies to improve efficiency.")
                with st.expander("🚨 **Urgent Tax Optimization Needed**", expanded=True):
                    st.markdown("""
                    ### ⚠️ **Your Tax Efficiency Needs Immediate Attention**
                    
                    **Priority Actions:**
                    1. **Review asset allocation** across account types
                    2. **Maximize tax-advantaged contributions** (401k, IRA, HSA)
                    3. **Consider Roth conversions** if in lower tax bracket
                    4. **Optimize fund selection** for tax efficiency
                    
                    **Quick Wins:**
                    - Switch to index funds (lower turnover = less taxes)
                    - Use tax-loss harvesting strategies
                    - Consider municipal bonds for taxable accounts
                    - Maximize HSA contributions if eligible
                    
                    📞 **Recommendation**: Consult a financial advisor for comprehensive tax optimization strategy.
                    """)
    
            with detail_tab3:
                # Summary table
                summary_data = {
                    "Metric": [
                        "Years Until Retirement",
                        "Total Future Value (Pre-Tax)",
                        "Total After-Tax Balance", 
                        "Total Tax Liability",
                        "Tax Efficiency (%)"
                    ],
                    "Value": [
                        f"{result['Years Until Retirement']:.0f} years",
                        f"${result['Total Future Value (Pre-Tax)']:,.0f}",
                        f"${result['Total After-Tax Balance']:,.0f}",
                        f"${result['Total Tax Liability']:,.0f}",
                        f"{result['Tax Efficiency (%)']:.1f}%"
                    ]
                }
                
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
                
                # PDF Report Download
                st.markdown("---")
                st.subheader("📄 Download Report")
                
                if _REPORTLAB_AVAILABLE:
                    try:
                        # Prepare user inputs for PDF
                        user_inputs = {
                            'client_name': client_name if client_name else 'Client',
                            'current_marginal_tax_rate_pct': current_tax_rate,
                            'retirement_marginal_tax_rate_pct': retirement_tax_rate,
                            'inflation_rate_pct': inflation_rate,
                            'age': age,
                            'retirement_age': retirement_age,
                            'life_expectancy': life_expectancy,
                            'annual_income': annual_income,
                            'birth_year': birth_year,
                            'retirement_income_goal': retirement_income_goal
                        }
                        
                        # Generate PDF
                        pdf_bytes = generate_pdf_report(result, assets, user_inputs)
                        
                        # Download button with personalized filename
                        client_name_clean = client_name.replace(" ", "_").replace(",", "").replace(".", "") if client_name else "Client"
                        filename = f"retirement_analysis_{client_name_clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                        
                        st.download_button(
                            label="📥 Download PDF Report",
                            data=pdf_bytes,
                            file_name=filename,
                            mime="application/pdf",
                            help="Download a comprehensive PDF report with all your retirement analysis details"
                        )
                        
                        st.info("💡 **PDF Report includes:** Executive summary, portfolio breakdown, individual asset projections, tax analysis, and personalized recommendations.")
                        
                    except Exception as e:
                        st.error(f"❌ Error generating PDF: {str(e)}")
                        st.info("💡 Try refreshing the page and running the analysis again.")
                else:
                    st.warning("⚠️ **PDF generation not available.** Install reportlab to enable PDF downloads:")
                    st.code("pip install reportlab", language="bash")
                
                st.success("✅ **Stage 2 analysis completed!** Next: Monte Carlo simulation and AI optimization.")
    
except Exception as e:
    st.error(f"❌ **Error in calculation**: {e}")
    with st.expander("🔍 Error Details", expanded=False):
        st.exception(e)

# Version footer
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: #666; font-size: 0.8em; padding: 10px;'>
        <strong>Financial Advisor v{VERSION}</strong> | 
        Advanced Retirement Planning with Asset Classification & Tax Optimization
    </div>
    """, 
    unsafe_allow_html=True
)


# ---------------------------
# Tests (unittest)
# ---------------------------

import unittest


class TestComputation(unittest.TestCase):
    def test_years_to_retirement_basic(self):
        self.assertEqual(years_to_retirement(30, 65), 35)

    def test_years_to_retirement_invalid(self):
        with self.assertRaises(ValueError):
            years_to_retirement(65, 60)

    def test_future_value_zero_rate(self):
        fv = future_value_with_contrib(10000, 1000, 0.0, 5)
        # 10k principal + 5*1k contributions
        self.assertAlmostEqual(fv, 15000.0, places=6)

    def test_future_value_positive_rate(self):
        # P=0, C=1000, r=10%, t=2  => 1000*((1.1^2 - 1)/0.1) = 1000*(0.21/0.1)=2100
        fv = future_value_with_contrib(0.0, 1000.0, 10.0, 2)
        self.assertAlmostEqual(fv, 2100.0, places=6)

    def test_post_tax_bounds(self):
        self.assertAlmostEqual(simple_post_tax(1000, 0), 1000.0)
        self.assertAlmostEqual(simple_post_tax(1000, 100), 0.0)
        self.assertAlmostEqual(simple_post_tax(1000, 25), 750.0)

    def test_asset_creation(self):
        asset = Asset(
            name="Test 401(k)",
            asset_type=AssetType.PRE_TAX,
            current_balance=10000,
            annual_contribution=5000,
            growth_rate_pct=7.0
        )
        self.assertEqual(asset.name, "Test 401(k)")
        self.assertEqual(asset.asset_type, AssetType.PRE_TAX)
        self.assertEqual(asset.current_balance, 10000)
        self.assertEqual(asset.annual_contribution, 5000)
        self.assertEqual(asset.growth_rate_pct, 7.0)

    def test_asset_growth_calculation(self):
        asset = Asset(
            name="Test Asset",
            asset_type=AssetType.PRE_TAX,
            current_balance=10000,
            annual_contribution=1000,
            growth_rate_pct=10.0
        )
        future_value, total_contributions = calculate_asset_growth(asset, 2)
        # Manual calculation: 10000 * 1.1^2 + 1000 * ((1.1^2 - 1)/0.1)
        # = 12100 + 1000 * (0.21/0.1) = 12100 + 2100 = 14200
        self.assertAlmostEqual(future_value, 14200.0, places=2)
        self.assertEqual(total_contributions, 2000.0)

    def test_tax_logic_pre_tax(self):
        asset = Asset(
            name="401(k)",
            asset_type=AssetType.PRE_TAX,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0
        )
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 0, 25.0)
        self.assertEqual(after_tax, 75000.0)
        self.assertEqual(tax_liability, 25000.0)

    def test_tax_logic_roth_ira(self):
        asset = Asset(
            name="Roth IRA",
            asset_type=AssetType.POST_TAX,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0
        )
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 0, 25.0)
        self.assertEqual(after_tax, 100000.0)
        self.assertEqual(tax_liability, 0.0)

    def test_tax_logic_brokerage(self):
        asset = Asset(
            name="Brokerage Account",
            asset_type=AssetType.POST_TAX,
            current_balance=0,
            annual_contribution=0,
            growth_rate_pct=0,
            tax_rate_pct=15.0
        )
        # 100k future value, 50k contributions = 50k gains
        after_tax, tax_liability = apply_tax_logic(asset, 100000, 50000, 25.0)
        expected_tax = 50000 * 0.15  # 15% on gains
        self.assertEqual(after_tax, 100000 - expected_tax)
        self.assertEqual(tax_liability, expected_tax)

    def test_project_enhanced(self):
        assets = [
            Asset(
                name="401(k)",
                asset_type=AssetType.PRE_TAX,
                current_balance=0,
                annual_contribution=10000,
                growth_rate_pct=10.0
            )
        ]
        inputs = UserInputs(
            age=30,
            retirement_age=31,
            life_expectancy=85,
            annual_income=100000,
            contribution_rate_pct=10,
            expected_growth_rate_pct=10,
            inflation_rate_pct=0,
            current_marginal_tax_rate_pct=22,
            retirement_marginal_tax_rate_pct=25,
            assets=assets
        )
        res = project(inputs)
        self.assertIn("Total Future Value (Pre-Tax)", res)
        self.assertIn("Total After-Tax Balance", res)
        self.assertIn("Tax Efficiency (%)", res)
        # FV should be ~ 10000 contribution grown 1 year at 10% = 11000
        # But with 0 principal, it's just the contribution: 10000
        self.assertAlmostEqual(res["Total Future Value (Pre-Tax)"], 10000.0, places=2)
        # After tax @25% = 7500
        self.assertAlmostEqual(res["Total After-Tax Balance"], 7500.0, places=2)

    def test_irs_tax_brackets(self):
        brackets = get_irs_tax_brackets_2024()
        self.assertEqual(len(brackets), 7)
        self.assertEqual(brackets[0].rate_pct, 10.0)
        self.assertEqual(brackets[-1].rate_pct, 37.0)

    def test_tax_rate_projection(self):
        brackets = get_irs_tax_brackets_2024()
        # Test various income levels
        self.assertEqual(project_tax_rate(5000, brackets), 10.0)   # First bracket
        self.assertEqual(project_tax_rate(30000, brackets), 12.0)  # Second bracket
        self.assertEqual(project_tax_rate(100000, brackets), 24.0) # Fourth bracket


# ---------------------------
# Entrypoint
# ---------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Financial Advisor - Stage 2: Advanced Retirement Planning")
    p.add_argument("--run-tests", action="store_true", help="Run unit tests and exit")
    return p


# Test runner - only runs when called with --run-tests
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and "--run-tests" in sys.argv:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestComputation)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        print("🚀 Financial Advisor - Advanced Retirement Planning")
        print("=" * 60)
        print("\nThis application requires the Streamlit web interface.")
        print("\nTo run the application:")
        print("  streamlit run fin_advisor.py")
        print("\nThis will open your web browser with the interactive interface.")
        print("\nFor testing, use:")
        print("  python fin_advisor.py --run-tests")
