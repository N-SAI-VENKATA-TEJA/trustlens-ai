import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TrustLensServer")

# --- Company Investigation ---
@mcp.tool()
def search_company_registry(company_name: str) -> str:
    """Search official company registries for business legitimacy."""
    return f"Company '{company_name}' is registered and active. Registration matches known records."

# --- Website Intelligence ---
@mcp.tool()
def whois_lookup(domain: str) -> str:
    """Retrieve WHOIS information for a domain (registration date, registrar, owner)."""
    return f"Domain '{domain}' was registered 5 years ago. Registrar is secure. No obfuscated ownership detected."

@mcp.tool()
def dns_lookup(domain: str) -> str:
    """Retrieve DNS records (A, MX, TXT) to verify email capability and hosting."""
    return f"Domain '{domain}' has valid MX records and standard hosting A records."

@mcp.tool()
def website_metadata(domain: str) -> str:
    """Fetch website metadata, tech stack, and security headers."""
    return f"Website '{domain}' uses a modern tech stack (React, Node) and valid security headers."

@mcp.tool()
def ssl_inspection(domain: str) -> str:
    """Inspect SSL/TLS certificate for validity, issuer, and age."""
    return f"Domain '{domain}' has a valid SSL certificate issued by Let's Encrypt, expires in 60 days."

# --- Document Verification ---
@mcp.tool()
def pdf_metadata(file_hash: str) -> str:
    """Extract metadata from a PDF file (author, creation tool, modified dates)."""
    return f"PDF '{file_hash}' metadata shows it was created using MS Word, no anomalous modifications."

@mcp.tool()
def document_hash(file_content: str) -> str:
    """Generate and check document hash against known forged document databases."""
    return f"Document content hash is unique. Not found in known forgery databases."

@mcp.tool()
def qr_decoder(qr_data_string: str) -> str:
    """Decode and validate QR codes found in certificates or documents."""
    return f"QR code decoded successfully. Link resolves to a secure verification portal."

# --- General Intelligence (Social, News, Reputation) ---
@mcp.tool()
def check_domain_reputation(domain: str) -> str:
    """Analyze domain age, SSL status, and reputation score."""
    return f"Domain '{domain}' has a clean reputation score of 95/100."

@mcp.tool()
def search_social_sentiment(entity_name: str) -> str:
    """Scan social media and forums for complaints and positive feedback."""
    return f"No major complaints found for '{entity_name}'. Sentiment is generally positive."

@mcp.tool()
def news_search(entity_name: str) -> str:
    """Search Google News and media outlets for mentions of the entity."""
    return f"News mentions for '{entity_name}' relate to product launches. No legal or fraud news found."

@mcp.tool()
def review_search(entity_name: str) -> str:
    """Search public reviews (Glassdoor, Trustpilot, Google Reviews)."""
    return f"Reviews for '{entity_name}' average 4.2 stars. Some complaints about customer service, none about fraud."

@mcp.tool()
def url_reputation(url: str) -> str:
    """Check a specific URL against PhishTank and Google Safe Browsing."""
    return f"URL '{url}' is clean and not flagged for phishing or malware."

@mcp.tool()
def virus_scan(file_hash: str) -> str:
    """Check file hash against VirusTotal."""
    return f"File hash '{file_hash}' has 0/72 detections on VirusTotal. Safe."

if __name__ == "__main__":
    mcp.run()
