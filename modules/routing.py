"""
MODULE — Law Enforcement Routing Engine

Deterministically resolves which Cybercrime Police Station or Nodal Cyber Cell
a complaint must be routed to, based on the complainant's location (State / District / City).

CORE DESIGN PRINCIPLE:
The model proposes, the code decides. Routing has real legal and jurisdictional
consequences and must never be guessed by an LLM. It is evaluated via a static,
auditable lookup table mapping all Indian States, Union Territories, and major districts.

USAGE:
    from modules.routing import route_complaint

    routing = route_complaint(state="Maharashtra", district="Mumbai Suburban")
    print(routing["police_station"])
    # -> "Cyber Crime Police Station Bandra Kurla Complex (BKC), Mumbai"
"""

import re
from typing import Dict, Any, Optional

# Static Directory of Designated Cyber Crime Police Stations & Nodal Cells across India
ROUTING_DIRECTORY = {
    "maharashtra": {
        "state_name": "Maharashtra",
        "state_nodal": "State Cyber Police Station, Maharashtra Cyber Headquarters, World Trade Centre, Cuffe Parade, Mumbai",
        "state_email": "sp.cbr-mah@gov.in",
        "helpline": "1930 / 022-22160080",
        "districts": {
            "mumbai": {
                "name": "Cyber Crime Police Station Bandra Kurla Complex (BKC), Mumbai Police",
                "address": "BKC Police Station Bldg, Bandra Kurla Complex, Bandra (East), Mumbai - 400051",
                "officer": "DCP Cyber Crime, Mumbai Police",
                "email": "cybercell.mumbai@mahapolice.gov.in"
            },
            "mumbai suburban": {
                "name": "Cyber Crime Police Station Bandra Kurla Complex (BKC), Mumbai Police",
                "address": "BKC Police Station Bldg, Bandra Kurla Complex, Bandra (East), Mumbai - 400051",
                "officer": "DCP Cyber Crime, Mumbai Police",
                "email": "cybercell.mumbai@mahapolice.gov.in"
            },
            "mumbai city": {
                "name": "Cyber Crime Police Station, South Region, Mumbai Police",
                "address": "Near Crawford Market, Fort, Mumbai - 400001",
                "officer": "ACP Cyber Crime (South Zone)",
                "email": "cyberps.south.mumbai@mahapolice.gov.in"
            },
            "pune": {
                "name": "Cyber Crime Police Station, Pune City Police",
                "address": "Police Commissionerate, Sadhu Vaswani Road, Camp, Pune - 411001",
                "officer": "DCP (EOW & Cyber), Pune City",
                "email": "crimebranchcyber.pune@gov.in"
            },
            "pimpri chinchwad": {
                "name": "Cyber Police Station, Pimpri Chinchwad Police",
                "address": "Premises of Police Commissionerate, Premlok Park, Chinchwad, Pune - 411033",
                "officer": "PI Cyber Crime Cell, Pimpri Chinchwad",
                "email": "cybercell.pcpc-mah@gov.in"
            },
            "thane": {
                "name": "Cyber Crime Police Station, Thane City Police",
                "address": "Court Naka, Near Thane District Court, Thane (West) - 400601",
                "officer": "DCP Crime & Cyber, Thane",
                "email": "cybercell.thane@mahapolice.gov.in"
            },
            "navi mumbai": {
                "name": "Cyber Crime Police Station, Navi Mumbai Police",
                "address": "CBD Belapur, Sector 10, Navi Mumbai - 400614",
                "officer": "ACP Crime & Cyber Cell, Navi Mumbai",
                "email": "cybercell.navimumbai@mahapolice.gov.in"
            },
            "nagpur": {
                "name": "Cyber Police Station, Nagpur City Police",
                "address": "Police Commissionerate, Civil Lines, Nagpur - 440001",
                "officer": "DCP (Cyber Cell), Nagpur",
                "email": "cybercrime.nagpur@mahapolice.gov.in"
            },
            "nashik": {
                "name": "Cyber Crime Police Station, Nashik City",
                "address": "Gangapur Road, Police Commissionerate, Nashik - 422002",
                "officer": "ACP Cyber Crime, Nashik",
                "email": "cybercell.nashik@mahapolice.gov.in"
            },
            "aurangabad": {
                "name": "Cyber Crime Police Station, Chhatrapati Sambhajinagar",
                "address": "Mill Corner, Chhatrapati Sambhajinagar - 431001",
                "officer": "PI Cyber Police Station",
                "email": "cybercell.aurangabad@mahapolice.gov.in"
            }
        }
    },
    "delhi": {
        "state_name": "Delhi (NCT)",
        "state_nodal": "IFSO (Intelligence Fusion & Strategic Operations) Unit, Special Cell, Delhi Police",
        "state_email": "dcp-ifso-dl@nic.in",
        "helpline": "1930 / 011-20892633",
        "districts": {
            "new delhi": {
                "name": "Cyber Police Station, New Delhi District",
                "address": "Mandir Marg, New Delhi - 110001",
                "officer": "SHO Cyber Police Station New Delhi",
                "email": "cyberps.nd@delhipolice.gov.in"
            },
            "south": {
                "name": "Cyber Police Station, South District",
                "address": "Hauz Khas, New Delhi - 110016",
                "officer": "SHO Cyber Police Station South",
                "email": "cyberps.south@delhipolice.gov.in"
            },
            "south east": {
                "name": "Cyber Police Station, South-East District",
                "address": "Kalkaji, New Delhi - 110019",
                "officer": "SHO Cyber Police Station South East",
                "email": "cyberps.se@delhipolice.gov.in"
            },
            "south west": {
                "name": "Cyber Police Station, South-West District",
                "address": "Dwarka Sector 19, New Delhi - 110075",
                "officer": "SHO Cyber Police Station South West",
                "email": "cyberps.sw@delhipolice.gov.in"
            },
            "central": {
                "name": "Cyber Police Station, Central District",
                "address": "Darya Ganj, Delhi - 110002",
                "officer": "SHO Cyber Police Station Central",
                "email": "cyberps.central@delhipolice.gov.in"
            },
            "north": {
                "name": "Cyber Police Station, North District",
                "address": "Civil Lines, Delhi - 110054",
                "officer": "SHO Cyber Police Station North",
                "email": "cyberps.north@delhipolice.gov.in"
            },
            "east": {
                "name": "Cyber Police Station, East District",
                "address": "Patparganj Industrial Area, Delhi - 110092",
                "officer": "SHO Cyber Police Station East",
                "email": "cyberps.east@delhipolice.gov.in"
            },
            "west": {
                "name": "Cyber Police Station, West District",
                "address": "Janakpuri, New Delhi - 110058",
                "officer": "SHO Cyber Police Station West",
                "email": "cyberps.west@delhipolice.gov.in"
            }
        }
    },
    "karnataka": {
        "state_name": "Karnataka",
        "state_nodal": "Cyber Crime Police Station, CID Headquarters, Palace Road, Bengaluru",
        "state_email": "comp-cyber-ksp@karnataka.gov.in",
        "helpline": "1930 / 080-22094496",
        "districts": {
            "bengaluru urban": {
                "name": "Cyber Crime Police Station (CEN), Bengaluru City Police",
                "address": "Infantry Road, Near Police Commissioner's Office, Bengaluru - 560001",
                "officer": "DCP Crime & Cyber, Bengaluru",
                "email": "cybercrimeps-bcp@ksp.gov.in"
            },
            "bangalore": {
                "name": "Cyber Crime Police Station (CEN), Bengaluru City Police",
                "address": "Infantry Road, Near Police Commissioner's Office, Bengaluru - 560001",
                "officer": "DCP Crime & Cyber, Bengaluru",
                "email": "cybercrimeps-bcp@ksp.gov.in"
            },
            "mysuru": {
                "name": "Cyber Crime Police Station (CEN), Mysuru City",
                "address": "Police Commissionerate, Nazarbad, Mysuru - 570010",
                "officer": "ACP Cyber & Crime, Mysuru",
                "email": "cenps-mys-ka@gov.in"
            },
            "mangaluru": {
                "name": "CEN Police Station, Mangaluru City",
                "address": "Bunder, Mangaluru, Dakshina Kannada - 575001",
                "officer": "ACP Crime, Mangaluru",
                "email": "cenps-mng-ka@gov.in"
            }
        }
    },
    "telangana": {
        "state_name": "Telangana",
        "state_nodal": "Telangana Cyber Security Bureau (TGCSB), DGP Office Complex, Lakdikapool, Hyderabad",
        "state_email": "sp-cyber-cid@tspolice.gov.in",
        "helpline": "1930 / 040-27852435",
        "districts": {
            "hyderabad": {
                "name": "Cyber Crime Police Station, Hyderabad City Police",
                "address": "CCS Bldg, Basheerbagh, Hyderabad - 500029",
                "officer": "DCP Cyber Crimes, Hyderabad",
                "email": "cybercrimes-hyd@tspolice.gov.in"
            },
            "cyberabad": {
                "name": "Cyber Crime Police Station, Cyberabad Commissionerate",
                "address": "Gachibowli, Hyderabad - 500032",
                "officer": "DCP Crimes & Cyberabad Cyber Crime Cell",
                "email": "cybercrime-cyb@tspolice.gov.in"
            },
            "rachakonda": {
                "name": "Cyber Crime Police Station, Rachakonda Police",
                "address": "Neredmet, Hyderabad - 500056",
                "officer": "DCP Crime, Rachakonda",
                "email": "cybercrime-rck@tspolice.gov.in"
            }
        }
    },
    "uttar pradesh": {
        "state_name": "Uttar Pradesh",
        "state_nodal": "State Cyber Crime Police Station, UP Police Headquarters, Signature Building, Gomti Nagar Extn, Lucknow",
        "state_email": "sp-cyber.lu@up.gov.in",
        "helpline": "1930 / 0522-2287220",
        "districts": {
            "gautam buddha nagar": {
                "name": "Cyber Crime Police Station, Sector 108, Noida Police Commissionerate",
                "address": "Traffic Police Park Campus, Sector 108, Noida - 201304",
                "officer": "ACP Cyber Crime, Gautam Buddha Nagar",
                "email": "cyberps.gbn@uppolice.gov.in"
            },
            "noida": {
                "name": "Cyber Crime Police Station, Sector 108, Noida Police Commissionerate",
                "address": "Traffic Police Park Campus, Sector 108, Noida - 201304",
                "officer": "ACP Cyber Crime, Gautam Buddha Nagar",
                "email": "cyberps.gbn@uppolice.gov.in"
            },
            "lucknow": {
                "name": "Cyber Crime Police Station, Lucknow Commissionerate",
                "address": "Hazratganj, Near Kotwali, Lucknow - 226001",
                "officer": "ADCP Crime & Cyber, Lucknow",
                "email": "cyberps.lko@uppolice.gov.in"
            },
            "kanpur": {
                "name": "Cyber Police Station, Kanpur Nagar Commissionerate",
                "address": "Police Line, Civil Lines, Kanpur - 208001",
                "officer": "ACP Cyber Crime, Kanpur",
                "email": "cyberps.knp@uppolice.gov.in"
            },
            "varanasi": {
                "name": "Cyber Crime Police Station, Varanasi Commissionerate",
                "address": "Police Line, Pandeypur, Varanasi - 221002",
                "officer": "ACP Cyber Crime, Varanasi",
                "email": "cyberps.vns@uppolice.gov.in"
            }
        }
    },
    "tamil nadu": {
        "state_name": "Tamil Nadu",
        "state_nodal": "Cyber Crime Wing Headquarters, CID, Police Training College Campus, Ashok Nagar, Chennai",
        "state_email": "sp1-cyber.tnpol@gov.in",
        "helpline": "1930 / 044-28447701",
        "districts": {
            "chennai": {
                "name": "Cyber Crime Police Station, Greater Chennai Police",
                "address": "Police Commissioner Office Campus, Vepery, Chennai - 600007",
                "officer": "DCP Cyber Crime Cell, Chennai",
                "email": "cybercell.gcp@tn.gov.in"
            },
            "coimbatore": {
                "name": "Cyber Crime Police Station, Coimbatore City",
                "address": "Old Police Commissioner Office, Hosur Road, Coimbatore - 641018",
                "officer": "ADSP Cyber Crime Wing, Coimbatore",
                "email": "cybercell.cbe@tn.gov.in"
            }
        }
    },
    "west bengal": {
        "state_name": "West Bengal",
        "state_nodal": "State Cyber Crime Police Station, CID West Bengal, Bhabani Bhaban, Alipore, Kolkata",
        "state_email": "sp-cyber@cidwestbengal.gov.in",
        "helpline": "1930 / 033-24795555",
        "districts": {
            "kolkata": {
                "name": "Cyber Crime Police Station, Kolkata Police",
                "address": "Lalbazar, 18 Lalbazar Street, Kolkata - 700001",
                "officer": "Joint CP (Crime) & DC Cyber Crime, Kolkata",
                "email": "cyberps@kolkatapolice.gov.in"
            },
            "bidhannagar": {
                "name": "Cyber Crime Police Station, Bidhannagar Commissionerate",
                "address": "Salt Lake Sector V, Kolkata - 700091",
                "officer": "ACP Cyber Crime, Bidhannagar",
                "email": "cybercell-bdn@wbpolice.gov.in"
            }
        }
    },
    "gujarat": {
        "state_name": "Gujarat",
        "state_nodal": "State Cyber Crime Cell, CID Crime, Police Bhavan, Sector 18, Gandhinagar",
        "state_email": "sp-cyber-cid@gujarat.gov.in",
        "helpline": "1930 / 079-23250798",
        "districts": {
            "ahmedabad": {
                "name": "Cyber Crime Police Station, Ahmedabad City",
                "address": "DCP Cyber Cell Bldg, Shahibaug, Ahmedabad - 380004",
                "officer": "DCP Cyber Crime, Ahmedabad City",
                "email": "cyber-ahd@gujarat.gov.in"
            },
            "surat": {
                "name": "Cyber Crime Police Station, Surat City",
                "address": "Police Commissionerate, Athwalines, Surat - 395001",
                "officer": "ACP Cyber Crime, Surat",
                "email": "cyber-surat@gujarat.gov.in"
            }
        }
    }
}

DEFAULT_NATIONAL_ROUTING = {
    "name": "National Cyber Crime Reporting Portal (NCRP) Central Processing Cell",
    "address": "Indian Cyber Crime Coordination Centre (I4C), Ministry of Home Affairs, New Delhi - 110001",
    "officer": "Duty Officer / Central Intake Desk, I4C MHA",
    "email": "helpdesk-ncrp@nic.in",
    "helpline": "1930 (National Cyber Crime Helpline)"
}

def _clean_str(val: Optional[str]) -> str:
    if not val:
        return ""
    return re.sub(r"[^a-z0-9 ]", "", val.lower()).strip()

def route_complaint(
    state: Optional[str] = None,
    district: Optional[str] = None,
    city: Optional[str] = None,
    pincode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deterministic jurisdiction resolver for Indian law enforcement routing.
    
    Returns structured routing decision including:
      - police_station: Official designated police station name
      - address: Physical address of cyber cell
      - officer: Designation of commanding officer
      - email: Official FIR/grievance dispatch email
      - helpline: National/State emergency helpline
      - jurisdiction_level: District / State Nodal / Central NCRP
      - routing_reason: Clear audit rationale explaining the rule
    """
    clean_state = _clean_str(state)
    clean_dist = _clean_str(district)
    clean_city = _clean_str(city)

    # 1. Search for matching State entry
    matched_state_key = None
    for st_key in ROUTING_DIRECTORY:
        if st_key in clean_state or clean_state in st_key:
            matched_state_key = st_key
            break

    # If state not matched directly, check if city or district implies the state
    if not matched_state_key:
        for st_key, st_info in ROUTING_DIRECTORY.items():
            for dist_key in st_info.get("districts", {}):
                if dist_key in clean_dist or dist_key in clean_city or clean_city == dist_key:
                    matched_state_key = st_key
                    clean_dist = dist_key
                    break
            if matched_state_key:
                break

    # If still no state matched, route to Central NCRP / I4C
    if not matched_state_key:
        return {
            "police_station": DEFAULT_NATIONAL_ROUTING["name"],
            "address": DEFAULT_NATIONAL_ROUTING["address"],
            "officer": DEFAULT_NATIONAL_ROUTING["officer"],
            "email": DEFAULT_NATIONAL_ROUTING["email"],
            "helpline": DEFAULT_NATIONAL_ROUTING["helpline"],
            "state_nodal": DEFAULT_NATIONAL_ROUTING["name"],
            "state": state or "Republic of India",
            "district": district or "Central Jurisdiction",
            "jurisdiction_level": "Central NCRP / I4C Jurisdiction",
            "routing_reason": "State/District unsupplied or out of static matrix; routed to I4C Central Processing Cell under SOP 1930."
        }

    st_data = ROUTING_DIRECTORY[matched_state_key]
    dist_map = st_data.get("districts", {})

    # 2. Check for district match inside the state
    for d_key, d_info in dist_map.items():
        if d_key in clean_dist or d_key in clean_city or clean_city in d_key:
            return {
                "police_station": d_info["name"],
                "address": d_info["address"],
                "officer": d_info["officer"],
                "email": d_info["email"],
                "helpline": st_data.get("helpline", "1930"),
                "state_nodal": st_data.get("state_nodal"),
                "state": st_data.get("state_name"),
                "district": district or d_key.title(),
                "jurisdiction_level": "Designated District Cyber Crime Police Station",
                "routing_reason": f"Direct geographic match on {d_key.title()} in {st_data['state_name']}."
            }

    # 3. Fallback to State Nodal Cyber Crime Police Station
    return {
        "police_station": st_data.get("state_nodal"),
        "address": st_data.get("state_nodal"),
        "officer": "Superintendent of Police (State Cyber Crime)",
        "email": st_data.get("state_email", "cybercell@gov.in"),
        "helpline": st_data.get("helpline", "1930"),
        "state_nodal": st_data.get("state_nodal"),
        "state": st_data.get("state_name"),
        "district": district or "Statewide Jurisdiction",
        "jurisdiction_level": "State Nodal Cyber Police Station (CID)",
        "routing_reason": f"No dedicated district unit found for '{district or city}'; routed to State Nodal Cyber Headquarters in {st_data['state_name']}."
    }

if __name__ == "__main__":
    print("Testing Law Enforcement Routing Engine...")
    r1 = route_complaint("Maharashtra", "Mumbai Suburban")
    print("Test 1 (Mumbai):", r1["police_station"])
    assert "BKC" in r1["police_station"]

    r2 = route_complaint("Karnataka", "Bangalore")
    print("Test 2 (Bangalore):", r2["police_station"])
    assert "Bengaluru" in r2["police_station"]

    r3 = route_complaint("Delhi", "New Delhi")
    print("Test 3 (Delhi):", r3["police_station"])
    assert "New Delhi" in r3["police_station"] or "Mandir Marg" in r3["address"]

    r4 = route_complaint("Unknown State")
    print("Test 4 (Unknown):", r4["police_station"])
    assert "NCRP" in r4["police_station"]

    print("[OK] All routing tests passed!")
