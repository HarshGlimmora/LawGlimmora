"""Design tokens and shared enum vocabularies."""
from __future__ import annotations


COLORS = {
    "ink": "#0F1419",
    "ink_soft": "#22303C",
    "ink_mute": "#6B7280",
    "ink_faint": "#9AA3AD",
    "parchment": "#F6F2E9",
    "parchment_soft": "#FBF8F1",
    "card": "#FFFFFF",
    "rule": "#E4DDCC",
    "rule_soft": "#EFE9DA",
    "accent": "#7A4A1F",
    "accent_soft": "#A47650",
    "accent_wash": "#F1E6D6",
    "seal": "#7B1E3A",
    "success": "#2F5233",
    "success_wash": "#E6EDE5",
    "warning": "#9A6B12",
    "warning_wash": "#F4EAD0",
    "danger": "#7B1E3A",
    "danger_wash": "#F1DCE2",
}

FONTS = {
    "display": "'Fraunces', 'Cormorant Garamond', Georgia, serif",
    "body": "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif",
    "mono": "'IBM Plex Mono', Menlo, monospace",
}

GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&"
    "family=IBM+Plex+Sans:wght@300;400;500;600;700&"
    "family=IBM+Plex+Mono:wght@400;500&display=swap"
)


PRACTICE_AREAS = [
    "Commercial litigation",
    "Constitutional & writ",
    "Corporate & M&A",
    "Criminal defence",
    "Family & matrimonial",
    "Intellectual property",
    "Labour & employment",
    "Real estate & conveyancing",
    "Tax",
    "Arbitration & ADR",
    "Banking & finance",
    "Environmental",
    "General practice",
]

INDIAN_JURISDICTIONS = [
    "Supreme Court of India",
    "Delhi High Court",
    "Bombay High Court",
    "Calcutta High Court",
    "Madras High Court",
    "Karnataka High Court",
    "Allahabad High Court",
    "Gujarat High Court",
    "Punjab & Haryana High Court",
    "Telangana High Court",
    "Kerala High Court",
    "District Courts",
    "Consumer Forum",
    "NCLT / NCLAT",
    "Tribunals (Tax / Service / Other)",
    "Pan-India",
]

LANGUAGES = [
    "English", "Hindi", "Marathi", "Tamil", "Telugu", "Bengali",
    "Gujarati", "Kannada", "Malayalam", "Punjabi", "Urdu",
]

CASE_TYPES = [
    "Civil suit", "Writ petition", "Criminal complaint", "Arbitration",
    "Commercial dispute", "Family matter", "Tax appeal", "Consumer complaint",
    "Service matter", "Insolvency", "Other",
]

ROLES_IN_CASE = [
    "Counsel for petitioner", "Counsel for respondent",
    "Counsel for plaintiff", "Counsel for defendant",
    "Counsel for complainant", "Counsel for accused",
    "Counsel for claimant", "Co-counsel", "Advisory only",
]

URGENCY_LEVELS = ["Routine", "Elevated", "Urgent", "Critical"]
CONFIDENTIALITY_LEVELS = ["Standard", "Restricted", "Privileged", "Sealed"]
CASE_STATUSES = [
    "Drafting", "Filed", "Pending hearing", "Under arguments",
    "Reserved for judgment", "Disposed", "Settled", "On appeal",
]

WORKSPACE_THEMES = ["Parchment (light)", "Counsel (dark)"]
ROLE_LAWYER = "lawyer"
