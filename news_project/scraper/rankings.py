# CCF (China Computer Federation) Rankings - 2024 Revised Edition
# Focused on Human-Computer Interaction (HCI), AI, and Ubiquitous Computing

CCF_RANKINGS = {
    # --- HCI & Ubiquitous Computing (Class A) ---
    "CHI": "CCF A",
    "Human Factors in Computing Systems": "CCF A",
    
    "UIST": "CCF A",
    "User Interface Software and Technology": "CCF A",
    
    "CSCW": "CCF A",
    "Computer Supported Cooperative Work": "CCF A",
    
    "IMWUT": "CCF A",
    "Interactive Mobile Wearable Ubiquitous Technologies": "CCF A",
    
    "UbiComp": "CCF A",
    "Ubiquitous Computing": "CCF A",
    
    "TOCHI": "CCF A",
    "Transactions on Computer-Human Interaction": "CCF A",
    
    "TVCG": "CCF A",
    "Transactions on Visualization and Computer Graphics": "CCF A",
    
    # --- HCI & Ubiquitous Computing (Class B) ---
    "DIS": "CCF B",
    "Designing Interactive Systems": "CCF B",
    
    "IUI": "CCF B",
    "Intelligent User Interfaces": "CCF B",
    
    "MobileHCI": "CCF B",
    "Mobile Human-Computer Interaction": "CCF B",
    
    "IJHCS": "CCF B",
    "International Journal of Human-Computer Studies": "CCF B",
    
    "IwC": "CCF B",
    "Interacting with Computers": "CCF B",
    
    "Group": "CCF B",
    "Supporting Group Work": "CCF B",
    
    "EICS": "CCF B",
    "Engineering Interactive Computing Systems": "CCF B",
    
    "Multimedia": "CCF B", # Sometimes cross-listed
    
    # --- HCI & Ubiquitous Computing (Class C) ---
    "ASSETS": "CCF C",
    "Computers and Accessibility": "CCF C",
    
    "GI": "CCF C",
    "Graphics Interface": "CCF C",
    
    "IDC": "CCF C",
    "Interaction Design and Children": "CCF C",
    
    "AVI": "CCF C",
    "Advanced Visual Interfaces": "CCF C",
    
    "UIC": "CCF C",
    "Ubiquitous Intelligence and Computing": "CCF C",
    
    "Ro-Man": "CCF C",
    "Robot and Human Interactive Communication": "CCF C",
    
    "INTERACT": "CCF C",
    "Human-Computer Interaction": "CCF C", # IFIP TC13
    
    "CollabTech": "CCF C",
    "Collaboration Technologies": "CCF C",
    
    "CSCWD": "CCF C",
    "Computer Supported Cooperative Work in Design": "CCF C",

    # --- Artificial Intelligence (Class A) ---
    "NeurIPS": "CCF A",
    "Neural Information Processing Systems": "CCF A",
    
    "ICML": "CCF A",
    "International Conference on Machine Learning": "CCF A",
    
    "AAAI": "CCF A",
    "AAAI Conference on Artificial Intelligence": "CCF A",
    
    "IJCAI": "CCF A",
    "International Joint Conference on Artificial Intelligence": "CCF A",
    
    "CVPR": "CCF A",
    "Computer Vision and Pattern Recognition": "CCF A",
    
    "ICCV": "CCF A",
    "International Conference on Computer Vision": "CCF A",
    
    "ACL": "CCF A",
    "Association for Computational Linguistics": "CCF A",
    
    "TPAMI": "CCF A",
    "Transactions on Pattern Analysis and Machine Intelligence": "CCF A",
    
    "IJCV": "CCF A",
    "International Journal of Computer Vision": "CCF A",
    
    "AI": "CCF A",
    "Artificial Intelligence": "CCF A",
    
    # --- Artificial Intelligence (Class B) ---
    "ECCV": "CCF B",
    "European Conference on Computer Vision": "CCF B",
    
    "EMNLP": "CCF B",
    "Empirical Methods in Natural Language Processing": "CCF B",
    
    "ECAI": "CCF B",
    "European Conference on Artificial Intelligence": "CCF B",
    
    "COLT": "CCF B",
    "Conference on Learning Theory": "CCF B",
    
    "KR": "CCF B",
    "Knowledge Representation and Reasoning": "CCF B",
    
    "CVIU": "CCF B",
    "Computer Vision and Image Understanding": "CCF B",

    # --- Artificial Intelligence (Class C) ---
    "IROS": "CCF C",
    "Intelligent Robots and Systems": "CCF C",
    
    "ICRA": "CCF C",
    "International Conference on Robotics and Automation": "CCF C",
    
    "BMVC": "CCF C",
    "British Machine Vision Conference": "CCF C",
    
    "ACCV": "CCF C",
    "Asian Conference on Computer Vision": "CCF C",
    
    "GECCO": "CCF C",
    "Genetic and Evolutionary Computation Conference": "CCF C",
    
    "ICTAI": "CCF C",
    "Tools with Artificial Intelligence": "CCF C",
    
    "NLPCC": "CCF C",
    "Natural Language Processing and Chinese Computing": "CCF C",
    
    # --- Computer Graphics & Multimedia (Selected) ---
    "SIGGRAPH": "CCF A",
    "SIGGRAPH Asia": "CCF A",
    
    "TOG": "CCF A",
    "Transactions on Graphics": "CCF A",
    
    "VR": "CCF A",
    "IEEE Virtual Reality": "CCF A",
    
    "MM": "CCF A",
    "ACM Multimedia": "CCF A",
    
    "ISMAR": "CCF B",
    "Mixed and Augmented Reality": "CCF B",
    
    "PG": "CCF B",
    "Pacific Graphics": "CCF B",
    
    "VRST": "CCF C",
    "VR Software and Technology": "CCF C",
}

# Impact Factors (Approximate 2024/2023 values)
# Used to calculate impact score if venue matches.
# Formula: Score = min(50, round(IF * 2))
JOURNAL_IFS = {
    "NATURE": 64.8,
    "SCIENCE": 56.9,
    "CELL": 64.5,
    "IEEE COMMUNICATIONS SURVEYS & TUTORIALS": 46.7,
    "SCIENCE ROBOTICS": 44.7,
    "INTERNATIONAL JOURNAL OF INFORMATION MANAGEMENT": 27.0,
    "NATURE BIOMEDICAL ENGINEERING": 26.6,
    "PROCEEDINGS OF THE IEEE": 25.9,
    "FOUNDATIONS AND TRENDS IN MACHINE LEARNING": 25.4,
    "TPAMI": 25.25,
    "TRANSACTIONS ON PATTERN ANALYSIS AND MACHINE INTELLIGENCE": 25.25,
    "NATURE MACHINE INTELLIGENCE": 23.9,
    "ACM COMPUTING SURVEYS": 23.8,
    "IEEE COMMUNICATIONS MAGAZINE": 22.1,
    "IEEE TRANSACTIONS ON IMAGE PROCESSING": 20.1,
    "IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS": 19.8,
    "IEEE-CAA JOURNAL OF AUTOMATICA SINICA": 19.2,
    "IEEE TRANSACTIONS ON WIRELESS COMMUNICATIONS": 18.6,
    "NATURE COMPUTATIONAL SCIENCE": 18.3,
    "IEEE INTERNET OF THINGS JOURNAL": 17.6,
    "PATTERN RECOGNITION": 17.3,
    "IEEE TRANSACTIONS ON COMMUNICATIONS": 16.3,
    "IEEE TRANSACTIONS ON NEURAL NETWORKS AND LEARNING SYSTEMS": 16.1,
    "INFORMATION FUSION": 15.5,
    "NPJ DIGITAL MEDICINE": 15.1,
    "AI OPEN": 14.8,
    "IEEE TRANSACTIONS ON INTELLIGENT VEHICLES": 14.3,
    "PHYSICS OF LIFE REVIEWS": 14.3,
    "JOURNAL OF MANUFACTURING SYSTEMS": 14.2,
    "IJCV": 12.0, # Approximate
    "INTERNATIONAL JOURNAL OF COMPUTER VISION": 12.0,
}

def get_ranking(text: str) -> str:
    """
    Search for the venue name in the text and return the text prepended with the ranking.
    Logic:
    1. Case insensitive search.
    2. Prioritize longer matches (e.g. 'SIGGRAPH Asia' over 'SIGGRAPH') to avoid partial match errors.
    """
    if not text:
        return ""
    
    upper_text = text.upper()
    # Sort keys by length descending to match full names before abbreviations
    keys = sorted(CCF_RANKINGS.keys(), key=len, reverse=True)
    
    for key in keys:
        # Simple substring check
        if key.upper() in upper_text:
            rank = CCF_RANKINGS[key]
            # Avoid double tagging if called multiple times or if text already has it
            if f"[{rank}]" in text:
                return text
            return f"[{rank}] {text}"
            
    return text

def get_venue_score(venue: str) -> int:
    """
    Calculate score based on venue reputation (CCF, Impact Factor).
    Returns basic score integer (0-50).
    """
    if not venue:
        return 0
    
    score = 0
    venue_upper = venue.upper()
    
    # 1. Check Impact Factor (High Precision)
    for j, if_val in JOURNAL_IFS.items():
        if j in venue_upper:
            # Score formula: IF * 2, capped at 50
            # e.g., TPAMI (25.25) -> 50. IEEE IoT (17.6) -> 35.
            return min(50, int(if_val * 2))
            
    # 2. Check CCF Rankings
    # A=50, B=25, C=10 (Aligned with core.py impact_score scale)
    
    # If already tagged with [CCF A], use that
    if "[CCF A]" in venue: return 50
    if "[CCF B]" in venue: return 25
    if "[CCF C]" in venue: return 10
        
    # Fallback: Check raw name if not yet tagged
    keys = sorted(CCF_RANKINGS.keys(), key=len, reverse=True)
    for key in keys:
        if key.upper() in venue_upper:
            rank = CCF_RANKINGS[key]
            if rank == "CCF A": return 50
            if rank == "CCF B": return 25
            if rank == "CCF C": return 10
            
    return 0
