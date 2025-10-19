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
"""

from __future__ import annotations
import argparse
import math
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

# Streamlit import
import streamlit as st
import io
import csv
from datetime import datetime

import pandas as pd

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
    years_in_retirement = 30
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
    if tax_efficiency > 85:
        recommendations.append("🎉 <b>Excellent tax efficiency!</b> Your portfolio is well-optimized.")
    elif tax_efficiency > 75:
        recommendations.append("⚠️ <b>Good tax efficiency</b>, but there may be room for improvement.")
    else:
        recommendations.append("🚨 <b>Consider tax optimization</b> strategies to improve efficiency.")
    
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
    
    # Footer
    story.append(Paragraph("This report was generated by the Financial Advisor - Stage 2 application.", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# Streamlit UI - this runs when using 'streamlit run fin_advisor.py'
st.set_page_config(page_title="Financial Advisor - Stage 2", layout="wide")
st.title("💰 Financial Advisor - Advanced Retirement Planning")

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

# Input Section with clear visual separation
st.markdown("---")
st.header("📝 Input Parameters")

# Create tabs for better organization
tab1, tab2, tab3 = st.tabs(["👤 Personal Info", "💰 Tax Settings", "🏦 Asset Configuration"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        # Birth year input instead of age
        current_year = datetime.now().year
        birth_year = st.number_input("Birth Year", min_value=current_year-90, max_value=current_year-18, value=current_year-30, help="Your birth year (age will be calculated automatically)")
        age = current_year - birth_year
        st.info(f"📅 **Current Age**: {age} years old")
        
        retirement_age = st.number_input("Target Retirement Age", min_value=40, max_value=80, value=65, help="When you plan to retire")
        st.info(f"⏰ **Years to Retirement**: {retirement_age - age} years")
    with col2:
        annual_income = st.number_input("Annual Income ($)", min_value=10000, value=85000, step=1000, help="Your current annual income")
        
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
            value=int(suggested_retirement_income), 
            step=1000, 
            help=f"Based on 75% replacement ratio: ${suggested_retirement_income:,.0f}"
        )
        
        # Show replacement ratio
        replacement_ratio = (retirement_income_goal / annual_income) * 100
        st.info(f"📊 **Income Replacement Ratio**: {replacement_ratio:.1f}% of current income")
        
        # Client name for personalization
        client_name = st.text_input("Client Name (for report personalization)", value="", placeholder="Enter your name for the PDF report", help="Optional: Your name will appear on the PDF report")

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        # Current tax rate with helpful guidance
        st.subheader("📊 Current Tax Rate")
        with st.expander("💡 How to find your current tax rate", expanded=False):
            st.markdown("""
            **To find your current marginal tax rate:**
            1. **From your tax return**: Look at your most recent Form 1040, Line 15 (Taxable Income)
            2. **Use IRS tax brackets**: Find which bracket your income falls into
            3. **Online calculator**: Use IRS.gov tax bracket calculator
            4. **Tax software**: Most tax software shows your marginal rate
            
            **2024 Tax Brackets (Single):**
            - 10%: $0 - $11,600
            - 12%: $11,601 - $47,150  
            - 22%: $47,151 - $100,525
            - 24%: $100,526 - $191,950
            - 32%: $191,951 - $243,725
            - 35%: $243,726 - $609,350
            - 37%: $609,351+
            """)
        
        current_tax_rate = st.slider("Current Marginal Tax Rate (%)", 0, 50, 22, help="Your current tax bracket based on your income")
        
        # Retirement tax rate with guidance
        st.subheader("🏖️ Retirement Tax Rate")
        with st.expander("💡 How to estimate retirement tax rate", expanded=False):
            st.markdown("""
            **Consider these factors for retirement tax rate:**
            1. **Lower income**: Most people have lower income in retirement
            2. **Social Security**: Only 85% is taxable for most people
            3. **Roth withdrawals**: Tax-free if qualified
            4. **Required Minimum Distributions**: Start at age 73 (2024)
            5. **State taxes**: Some states don't tax retirement income
            
            **Common scenarios:**
            - **Conservative estimate**: Same as current rate
            - **Optimistic estimate**: 10-15% lower than current
            - **Pessimistic estimate**: 5-10% higher (if tax rates increase)
            """)
        
        retirement_tax_rate = st.slider("Projected Retirement Tax Rate (%)", 0, 50, 25, help="Expected tax rate in retirement (often lower than current)")
        
    with col2:
        # Inflation rate with guidance
        st.subheader("📈 Inflation Rate")
        with st.expander("💡 How to estimate inflation", expanded=False):
            st.markdown("""
            **Historical context:**
            - **Long-term average**: 3.0-3.5% annually
            - **Recent years**: 2-4% (2020-2024)
            - **Federal Reserve target**: 2% annually
            
            **Consider:**
            1. **Conservative estimate**: 2-3% (Fed target)
            2. **Moderate estimate**: 3-4% (historical average)
            3. **Aggressive estimate**: 4-5% (higher inflation periods)
            
            **Impact on retirement:**
            - Higher inflation = need more money in retirement
            - Affects purchasing power of fixed income
            - Consider inflation-protected investments (TIPS, I-Bonds)
            """)
        
        inflation_rate = st.slider("Expected Inflation Rate (%)", 0, 10, 3, help="Long-term inflation assumption (affects purchasing power)")

with tab3:
    # Quick setup options
    setup_option = st.radio(
        "Choose setup method:",
        ["Use Default Portfolio", "Upload CSV File", "Configure Individual Assets", "Legacy Mode (Simple)"],
        help="Select how you want to configure your retirement accounts"
    )

    assets = []

    if setup_option == "Use Default Portfolio":
        assets = create_default_assets()
        st.success("✅ Using default portfolio with 401(k), Roth IRA, Brokerage, and Savings accounts")
        
        # Show default portfolio details in editable table format
        with st.expander("📋 Default Portfolio Details (Editable)", expanded=True):
            # Create editable table data
            table_data = []
            for i, asset in enumerate(assets):
                row = {
                    "Index": i,
                    "Account": asset.name,
                    "Asset Type": asset.asset_type.value,
                    "Current Balance": asset.current_balance,
                    "Annual Contribution": asset.annual_contribution,
                    "Growth Rate (%)": asset.growth_rate_pct,
                    "Tax Rate (%)": asset.tax_rate_pct
                }
                table_data.append(row)
            
            # Create editable dataframe
            df = pd.DataFrame(table_data)
            
            # Define column configuration for editing
            column_config = {
                "Index": st.column_config.NumberColumn("Index", disabled=True, help="Asset index (read-only)"),
                "Account": st.column_config.TextColumn("Account Name", help="Name of the account"),
                "Asset Type": st.column_config.SelectboxColumn(
                    "Asset Type", 
                    options=["pre_tax", "post_tax", "tax_deferred"],
                    help="Tax treatment: pre_tax (401k/IRA), post_tax (Roth/Brokerage), tax_deferred (HSA/Annuities)"
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
                    help="Expected annual growth rate"
                ),
                "Tax Rate (%)": st.column_config.NumberColumn(
                    "Tax Rate (%)", 
                    min_value=0, 
                    max_value=50, 
                    format="%.1f%%",
                    help="Tax rate (0% for Roth, 15% for brokerage capital gains)"
                )
            }
            
            # Display editable table
            st.info("💡 **Edit the default portfolio directly in the table below. Changes will be applied when you run the analysis.**")
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
                        # Parse asset type
                        asset_type_str = row["Asset Type"]
                        if asset_type_str == "pre_tax":
                            asset_type = AssetType.PRE_TAX
                        elif asset_type_str == "post_tax":
                            asset_type = AssetType.POST_TAX
                        elif asset_type_str == "tax_deferred":
                            asset_type = AssetType.TAX_DEFERRED
                        else:
                            raise ValueError(f"Invalid asset type: {asset_type_str}")
                        
                        # Create updated asset
                        updated_asset = Asset(
                            name=row["Account"],
                            asset_type=asset_type,
                            current_balance=float(row["Current Balance"]),
                            annual_contribution=float(row["Annual Contribution"]),
                            growth_rate_pct=float(row["Growth Rate (%)"]),
                            tax_rate_pct=float(row["Tax Rate (%)"])
                        )
                        updated_assets.append(updated_asset)
                    
                    # Update the assets list
                    assets = updated_assets
                    st.success(f"✅ Default portfolio updated! {len(assets)} assets ready for analysis.")
                    
                except Exception as e:
                    st.error(f"❌ Error updating default portfolio: {str(e)}")
                    st.info("💡 Please check your input values and try again.")
    
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
                    # Create editable table data
                    table_data = []
                    for i, asset in enumerate(assets):
                        row = {
                            "Index": i,
                            "Account": asset.name,
                            "Asset Type": asset.asset_type.value,
                            "Current Balance": asset.current_balance,
                            "Annual Contribution": asset.annual_contribution,
                            "Growth Rate (%)": asset.growth_rate_pct,
                            "Tax Rate (%)": asset.tax_rate_pct
                        }
                        table_data.append(row)
                    
                    # Create editable dataframe
                    df = pd.DataFrame(table_data)
                    
                    # Define column configuration for editing
                    column_config = {
                        "Index": st.column_config.NumberColumn("Index", disabled=True, help="Asset index (read-only)"),
                        "Account": st.column_config.TextColumn("Account Name", help="Name of the account"),
                        "Asset Type": st.column_config.SelectboxColumn(
                            "Asset Type", 
                            options=["pre_tax", "post_tax", "tax_deferred"],
                            help="Tax treatment: pre_tax (401k/IRA), post_tax (Roth/Brokerage), tax_deferred (HSA/Annuities)"
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
                            help="Expected annual growth rate"
                        ),
                        "Tax Rate (%)": st.column_config.NumberColumn(
                            "Tax Rate (%)", 
                            min_value=0, 
                            max_value=50, 
                            format="%.1f%%",
                            help="Tax rate (0% for Roth, 15% for brokerage capital gains)"
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
                                # Parse asset type
                                asset_type_str = row["Asset Type"]
                                if asset_type_str == "pre_tax":
                                    asset_type = AssetType.PRE_TAX
                                elif asset_type_str == "post_tax":
                                    asset_type = AssetType.POST_TAX
                                elif asset_type_str == "tax_deferred":
                                    asset_type = AssetType.TAX_DEFERRED
                                else:
                                    raise ValueError(f"Invalid asset type: {asset_type_str}")
                                
                                # Create updated asset
                                updated_asset = Asset(
                                    name=row["Account"],
                                    asset_type=asset_type,
                                    current_balance=float(row["Current Balance"]),
                                    annual_contribution=float(row["Annual Contribution"]),
                                    growth_rate_pct=float(row["Growth Rate (%)"]),
                                    tax_rate_pct=float(row["Tax Rate (%)"])
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
                    growth_rate = st.slider(f"Growth Rate {i+1} (%)", 0, 20, 7, help="Expected annual return")
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

    else:  # Legacy mode
        st.info("📊 Legacy mode: Single blended calculation")
        contribution_rate = st.slider("Annual Savings Rate (% of income)", 0, 50, 15, help="Percentage of income you save")
        current_balance = st.number_input("Current Total Savings ($)", min_value=0, value=50000, step=1000, help="Total current savings")
        expected_growth_rate = st.slider("Expected Annual Growth Rate (%)", 0, 20, 7, help="Expected annual return")
        
        # Create legacy asset
        total_contribution = annual_income * (contribution_rate / 100.0)
        assets = [Asset(
            name="401(k) / Traditional IRA (Pre-Tax)",
            asset_type=AssetType.PRE_TAX,
            current_balance=current_balance,
            annual_contribution=total_contribution,
            growth_rate_pct=expected_growth_rate
        )]

# Results Section with clear visual separation
st.markdown("---")
st.header("📊 Retirement Projection Results")

try:
    inputs = UserInputs(
        age=int(age),
        retirement_age=int(retirement_age),
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
    years_in_retirement = 30  # Assume 30 years of retirement
    annual_retirement_income = total_after_tax / years_in_retirement
    
    # Calculate shortfall or surplus
    income_shortfall = retirement_income_goal - annual_retirement_income
    income_ratio = (annual_retirement_income / retirement_income_goal) * 100
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Projected Annual Income", 
            f"${annual_retirement_income:,.0f}",
            help="Based on 30-year retirement period"
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
        st.write("**Individual Asset Values (After-Tax)**")
        
        # Create asset breakdown
        asset_data = []
        for key, value in result.items():
            if "Asset" in key and "After-Tax" in key:
                asset_name = key.split(" - ")[1].replace(" (After-Tax)", "")
                asset_data.append({
                    "Account": asset_name,
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
                st.success("🎉 **Excellent tax efficiency!** Your portfolio is well-optimized.")
            elif result["Tax Efficiency (%)"] > 75:
                st.warning("⚠️ **Good tax efficiency**, but there may be room for improvement.")
            else:
                st.error("🚨 **Consider tax optimization** strategies to improve efficiency.")
    
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
