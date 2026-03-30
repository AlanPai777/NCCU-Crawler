# ============================================================
#  config.py — NCCU crawler global settings
# ============================================================

# ── Entry Point ──────────────────────────────────────────────
START_URL      = "https://www.nccu.edu.tw"
ALLOWED_DOMAIN = "nccu.edu.tw"

# ── Crawl Limits ─────────────────────────────────────────────
MAX_DEPTH          = 999      # safety cap; deduplication prevents infinite loops
MAX_PAGES_TOTAL    = 500000   # effectively unlimited for full crawls
MAX_PAGES_PER_HOST = 10000    # per-subdomain cap
REQUEST_DELAY      = 0.5
REQUEST_TIMEOUT    = 15
MAX_CONCURRENCY    = 8
MAX_DOC_BYTES      = 200 * 1024 * 1024   # 200 MB per document

# ── Output Paths ─────────────────────────────────────────────
OUTPUT_DIR      = "output"
HTML_DIR        = "output/html"
DOCS_DIR        = "output/docs"
MAP_FILE        = "output/map.json"
CLASSIFIED_FILE = "output/classified.json"
PROGRESS_FILE   = "output/progress.json"
LOG_FILE        = "output/crawler.log"

# ── Document Extensions (saved to DOCS_DIR) ──────────────────
DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx",
    ".xls", ".xlsx",
    ".ppt", ".pptx",
    ".odt", ".ods", ".odp",
    ".txt", ".csv",
    ".zip", ".rar", ".gz",    # archives (typically regulation bundles or data exports)
}

# ── Ignored Extensions (neither HTML nor document — skip entirely) ────
IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    ".json", ".xml",
}

# ── Ignored URL Patterns ──────────────────────────────────────
IGNORED_URL_PATTERNS = [
    "mailto:", "tel:", "javascript:", "ftp:",
    "/login", "/logout", "/signin",
    "?download=", "?action=print",
    "feed=rss", "/cgi-bin/",
    "?replytocom=",
]

# ── Subdomain Category Mapping ────────────────────────────────
SUBDOMAIN_CATEGORIES = {
    # ── Main Site ─────────────────────────────────────────────
    "www":          "main",
    "":             "main",       # bare domain nccu.edu.tw

    # ── 12 Colleges ───────────────────────────────────────────
    "la":           "college_la",         # Liberal Arts
    "sc":           "college_sc",         # Social Sciences
    "ba":           "college_ba",         # Business Administration
    "comm":         "college_comm",       # Communication
    "llce":         "college_llce",       # Foreign Languages & Literatures
    "law":          "college_law",        # Law
    "s3g":          "college_sci",        # Science
    "education":    "college_edu",        # Education
    "ips":          "college_ips",        # International Affairs
    "x":            "college_x",          # X College (experimental)
    "coi":          "college_coi",        # Informatics
    "ibf":          "college_ibf",        # International Banking & Finance

    # ── Departments ───────────────────────────────────────────
    "cs":           "dept_cs",            # Computer Science
    "stat":         "dept_stat",          # Statistics
    "math":         "dept_math",          # Applied Mathematics
    "ephys":        "dept_ephys",         # Electronics & Physics
    "fin":          "dept_fin",           # Finance
    "econ":         "dept_econ",          # Economics
    "acc":          "dept_acc",           # Accounting
    "mba":          "dept_mba",           # Business Administration / MBA
    "ib":           "dept_ib",            # International Business
    "mis":          "dept_mis",           # Management Information Systems
    "oic":          "dept_oic",           # Business Administration (Graduate)
    "iep":          "dept_iep",           # Economics (Graduate)
    "imba":         "dept_imba",          # International MBA
    "po":           "dept_po",            # Political Science
    "dp":           "dept_dp",            # Diplomacy
    "gipo":         "dept_gipo",          # National Security & Mainland China Studies
    "psy":          "dept_psy",           # Psychology
    "soc":          "dept_soc",           # Sociology
    "sw":           "dept_sw",            # Social Work
    "npom":         "dept_npom",          # Non-Profit Organization Management
    "chi":          "dept_chi",           # Chinese Literature
    "his":          "dept_his",           # History
    "phil":         "dept_phil",          # Philosophy
    "libart":       "dept_libart",        # Library & Information Science
    "geo":          "dept_geo",           # Land Economics
    "llm":          "dept_llm",           # Law
    "cpcs":         "dept_cpcs",          # Comparative Studies
    "dptpe":        "dept_pe",            # Physical Education
    "nccu-pe":      "dept_pe",
    "arabic":       "dept_arabic",        # Arabic
    "russian":      "dept_russian",       # Slavic Languages
    "turkish":      "dept_turkish",       # Turkish
    "japanese":     "dept_japanese",      # Japanese
    "korean":       "dept_korean",        # Korean
    "german":       "dept_german",        # German
    "french":       "dept_french",        # French
    "english":      "dept_english",       # English
    "spanpor":      "dept_spanpor",       # Spanish & Portuguese

    # ── Administrative Units ──────────────────────────────────
    "aca":          "admin_academic",     # Office of Academic Affairs
    "sa":           "admin_student",      # Office of Student Affairs
    "rd":           "admin_rd",           # Office of Research & Development
    "ga":           "admin_general",      # General Affairs Office
    "info":         "admin_info",         # Information Technology Office
    "pr":           "admin_pr",           # Public Affairs Center
    "sec":          "admin_sec",          # Secretariat
    "opo":          "admin_opo",          # Alumni & Resource Development
    "oia":          "admin_oia",          # Office of International Cooperation
    "hr":           "admin_hr",           # Human Resources Office
    "audit":        "admin_audit",        # Accounting Office
    "dsa":          "admin_dsa",          # Student Counseling Center
    "aa":           "admin_aa",           # Alumni Services
    "military":     "admin_military",     # Military Training Office

    # ── Library ───────────────────────────────────────────────
    "lib":          "library",
    "nccuir":       "library",            # Institutional Repository
    "ah":           "library",            # Academic Hub
    "mcr":          "library",            # Journalism Research

    # ── Research Centers ──────────────────────────────────────
    "rcbe":         "research",           # Business Research Center
    "election":     "research",           # Election Study Center
    "iir":          "research",           # Institute of International Relations
    "rchss":        "research",           # Research Center for Humanities & Social Sciences
    "irpp":         "research",           # Institute for Public Policy Research
    "cmmw":         "research",           # Media & Culture Research
    "tigp":         "research",           # Taiwan International Graduate Program

    # ── Service Systems ───────────────────────────────────────
    "portal":       "service_portal",     # Student Portal (i.nccu.edu.tw)
    "i":            "service_portal",
    "moodle":       "service_lms",        # E-Learning Platform
    "lms":          "service_lms",
    "selectcourse": "service_course",     # Course Selection System
    "qrysub":       "service_course",
    "admission":    "service_admission",  # Admissions
    "oia-apply":    "service_admission",
    "vote":         "research",           # Election data
    "nccur":        "library",            # Institutional Repository (nccur.lib)
}

# ── Extra Seeds ───────────────────────────────────────────────
# Each subdomain is used as an independent seed to ensure subdomains
# not reachable from www.nccu.edu.tw are still crawled.
EXTRA_SEEDS = [
    f"https://{sub}.nccu.edu.tw"
    for sub in SUBDOMAIN_CATEGORIES
    if sub not in ("", "www")   # main site is already the default seed
]
