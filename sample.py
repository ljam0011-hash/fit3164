import requests
import json
from datetime import datetime, timedelta, timezone
import csv
import io
import time

# Base URL for the API
BASE_URL = "http://localhost:8000"

# Sample Google user data (simulating login2fa.py auth)
SAMPLE_GOOGLE_USERS = [
    {
        "id": "google_user_001",
        "email": "lumine@student.monash.edu",
        "name": "Lumine Traveler",
        "picture": "https://example.com/lumine.jpg"
    },
    {
        "id": "google_user_002",
        "email": "zhongli@student.monash.edu",
        "name": "Zhongli Rex",
        "picture": "https://example.com/zhongli.jpg"
    },
    {
        "id": "google_user_003",
        "email": "kaeya@student.monash.edu",
        "name": "Kaeya Alberich",
        "picture": "https://example.com/kaeya.jpg"
    },
    {
        "id": "google_user_004",
        "email": "collei@student.monash.edu",
        "name": "Collei Forest",
        "picture": "https://example.com/collei.jpg"
    },
    {
        "id": "google_user_005",
        "email": "itto@student.monash.edu",
        "name": "Arataki Itto",
        "picture": "https://example.com/itto.jpg"
    },
    {
        "id": "google_user_006",
        "email": "nahida@student.monash.edu",
        "name": "Nahida Kusanali",
        "picture": "https://example.com/nahida.jpg"
    }
]

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_menu():
    """Display the main menu"""
    print_header("MONASH VOTING SYSTEM - TEST MENU")
    print("\n1. Basic Election Flow (Create, Add Candidates, Vote)")
    print("2. Test Vote Integrity Verification")
    print("3. Test Audit Trail System")
    print("4. Test Bulk Candidate Import (JSON)")
    print("5. Test Bulk Candidate Import (CSV)")
    print("6. Test Election Templates")
    print("7. Test Vote Receipt Generation")
    print("8. Test Election Freeze/Unfreeze")
    print("9. View All Audit Logs")
    print("10. Run Complete Test Suite")
    print("0. Exit")
    print("\n" + "-"*60)

def test_basic_election_flow():
    """Test 1: Basic election creation, candidates, and voting"""
    print_header("TEST 1: BASIC ELECTION FLOW")
    
    # Get current UTC time
    utc_now = datetime.now(timezone.utc)
    
    # Create election
    print("\n1. Creating election...")
    election_data = {
        "title": "Student Council President Election 2025",
        "description": "Annual election for student council president",
        "start_time": (utc_now - timedelta(hours=1)).isoformat(),
        "end_time": (utc_now + timedelta(days=7)).isoformat()
    }
    
    response = requests.post(f"{BASE_URL}/api/elections", json=election_data)
    print(f"Response: {response.json()}")
    election_id = response.json()["election_id"]
    
    # Add candidates
    print("\n2. Adding candidates...")
    candidates = [
        {"name": "Alice Chen", "faculty": "Engineering", "manifesto": "Innovation and progress"},
        {"name": "Bob Smith", "faculty": "Business", "manifesto": "Financial responsibility"},
        {"name": "Carol Wang", "faculty": "Arts", "manifesto": "Creative expression"}
    ]
    
    candidate_ids = []
    for candidate in candidates:
        response = requests.post(f"{BASE_URL}/api/elections/{election_id}/candidates", json=candidate)
        print(f"Added: {candidate['name']}")
        candidate_ids.append(response.json()["candidate_id"])
    
    # Submit votes with Google auth
    print("\n3. Submitting votes with Google authentication...")
    votes_submitted = []
    
    for i, google_user in enumerate(SAMPLE_GOOGLE_USERS[:3]):
        vote_data = {
            "google_user_info": google_user,
            "election_id": election_id,
            "preferences": {
                str(candidate_ids[0]): (i % 3) + 1,
                str(candidate_ids[1]): ((i + 1) % 3) + 1,
                str(candidate_ids[2]): ((i + 2) % 3) + 1
            },
            "voter_traits": {
                "faculty": ["Engineering", "Business", "Arts"][i % 3],
                "gender": ["Male", "Female", "Other"][i % 3],
                "study_level": "Undergraduate",
                "year_level": (i % 4) + 1
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/vote", json=vote_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Vote {i+1}: {google_user['name']} - Confirmation: {result['confirmation_code']}")
            votes_submitted.append(result)
        else:
            print(f"✗ Vote {i+1}: Failed - {response.json()}")
    
    # Get results
    print("\n4. Election Results:")
    response = requests.get(f"{BASE_URL}/api/elections/{election_id}/results")
    results = response.json()
    print(f"Total votes: {results['total_votes']}")
    print(f"Vote counts: {json.dumps(results['vote_counts'], indent=2)}")
    
    return election_id, votes_submitted

def test_vote_verification():
    """Test 2: Vote integrity verification"""
    print_header("TEST 2: VOTE INTEGRITY VERIFICATION")
    
    # First create an election and submit a vote
    print("\nSetting up test election...")
    election_id, votes = test_basic_election_flow()
    
    if not votes:
        print("No votes to verify!")
        return
    
    print("\n" + "-"*40)
    print("Testing vote verification...")
    
    # Test valid verification
    confirmation_code = votes[0]['confirmation_code']
    print(f"\n1. Verifying with valid confirmation code: {confirmation_code}")
    
    verification_data = {
        "confirmation_code": confirmation_code,
        "google_id": SAMPLE_GOOGLE_USERS[0]['id']  # Optional additional verification
    }
    
    response = requests.post(f"{BASE_URL}/api/verify-vote", json=verification_data)
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Verification successful!")
        print(f"  - Status: {result['status']}")
        print(f"  - Election: {result['election_title']}")
        print(f"  - Voted at: {result['voted_at']}")
        print(f"  - Integrity check: {result['integrity_check']}")
    else:
        print(f"✗ Verification failed: {response.json()}")
    
    # Test invalid verification
    print(f"\n2. Verifying with invalid confirmation code...")
    verification_data = {"confirmation_code": "INVALID"}
    response = requests.post(f"{BASE_URL}/api/verify-vote", json=verification_data)
    print(f"Response: {response.status_code} - {response.json()['detail']}")
    
    # Test mismatched Google ID
    print(f"\n3. Verifying with mismatched Google ID...")
    verification_data = {
        "confirmation_code": confirmation_code,
        "google_id": "wrong_google_id"
    }
    response = requests.post(f"{BASE_URL}/api/verify-vote", json=verification_data)
    print(f"Response: {response.status_code} - {response.json().get('detail', 'Success')}")

def test_audit_trail():
    """Test 3: Audit trail system"""
    print_header("TEST 3: AUDIT TRAIL SYSTEM")
    
    # Create election and perform various actions
    print("\nPerforming administrative actions...")
    
    utc_now = datetime.now(timezone.utc)
    election_data = {
        "title": "Test Audit Election",
        "description": "Testing audit trail",
        "start_time": utc_now.isoformat(),
        "end_time": (utc_now + timedelta(days=1)).isoformat()
    }
    
    # Create election
    print("1. Creating election...")
    response = requests.post(f"{BASE_URL}/api/elections", json=election_data)
    election_id = response.json()["election_id"]
    
    # Add candidate
    print("2. Adding candidate...")
    candidate_data = {"name": "Test Candidate", "faculty": "Test Faculty"}
    requests.post(f"{BASE_URL}/api/elections/{election_id}/candidates", json=candidate_data)
    
    # Freeze election
    print("3. Freezing election...")
    requests.post(f"{BASE_URL}/api/elections/{election_id}/freeze")
    
    # Unfreeze election
    print("4. Unfreezing election...")
    requests.post(f"{BASE_URL}/api/elections/{election_id}/unfreeze")
    
    # Get audit logs
    print("\n" + "-"*40)
    print("Retrieving audit logs for this election...")
    response = requests.get(f"{BASE_URL}/api/audit-logs?election_id={election_id}")
    
    if response.status_code == 200:
        logs = response.json()
        print(f"\nFound {len(logs)} audit log entries:")
        for log in logs:
            print(f"\n  [{log['timestamp']}]")
            print(f"  Action: {log['action_type']}")
            print(f"  Actor: {log['actor_email']} (ID: {log['actor_id']})")
            print(f"  Details: {json.dumps(log['details'], indent=4)}")
    else:
        print(f"Failed to retrieve logs: {response.json()}")

def test_bulk_import_json():
    """Test 4: Bulk candidate import via JSON"""
    print_header("TEST 4: BULK CANDIDATE IMPORT (JSON)")
    
    # Create election
    utc_now = datetime.now(timezone.utc)
    election_data = {
        "title": "Bulk Import Test Election",
        "description": "Testing bulk candidate import",
        "start_time": utc_now.isoformat(),
        "end_time": (utc_now + timedelta(days=1)).isoformat()
    }
    
    print("\n1. Creating election...")
    response = requests.post(f"{BASE_URL}/api/elections", json=election_data)
    election_id = response.json()["election_id"]
    
    # Prepare bulk candidates
    bulk_candidates = {
        "candidates": [
            {"name": "Keqing", "faculty": "Electro", "manifesto": "Efficiency above all"},
            {"name": "Ganyu", "faculty": "Cryo", "manifesto": "Dedicated service"},
            {"name": "Xiao", "faculty": "Anemo", "manifesto": "Protection through strength"},
            {"name": "Hu Tao", "faculty": "Pyro", "manifesto": "Life and death balance"},
            {"name": "Yelan", "faculty": "Hydro", "manifesto": "Intelligence gathering"}
        ]
    }
    
    print(f"\n2. Importing {len(bulk_candidates['candidates'])} candidates via JSON...")
    response = requests.post(
        f"{BASE_URL}/api/elections/{election_id}/candidates/bulk",
        json=bulk_candidates
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ {result['message']}")
        print(f"  Candidate IDs: {result['candidate_ids']}")
    else:
        print(f"✗ Import failed: {response.json()}")
    
    # Verify candidates were added
    print("\n3. Verifying imported candidates...")
    response = requests.get(f"{BASE_URL}/api/elections/{election_id}/candidates")
    candidates = response.json()
    print(f"Total candidates in election: {len(candidates)}")
    for c in candidates:
        print(f"  - {c['name']} ({c['faculty']})")

def test_bulk_import_csv():
    """Test 5: Bulk candidate import via CSV"""
    print_header("TEST 5: BULK CANDIDATE IMPORT (CSV)")
    
    # Create election
    utc_now = datetime.now(timezone.utc)
    election_data = {
        "title": "CSV Import Test Election",
        "description": "Testing CSV candidate import",
        "start_time": utc_now.isoformat(),
        "end_time": (utc_now + timedelta(days=1)).isoformat()
    }
    
    print("\n1. Creating election...")
    response = requests.post(f"{BASE_URL}/api/elections", json=election_data)
    election_id = response.json()["election_id"]
    
    # Create CSV content
    csv_content = """name,faculty,manifesto,external_id
Jean Gunnhildr,Knights of Favonius,Leadership through example,KOF001
Diluc Ragnvindr,Dawn Winery,Independent protection,DW001
Kaeya Alberich,Knights of Favonius,Strategic planning,KOF002
Lisa Minci,Library,Knowledge is power,LIB001
Amber,Outriders,Enthusiasm and dedication,OUT001"""
    
    print("\n2. Importing candidates from CSV...")
    files = {'file': ('candidates.csv', csv_content, 'text/csv')}
    response = requests.post(
        f"{BASE_URL}/api/elections/{election_id}/candidates/csv",
        files=files
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ {result['message']}")
        print(f"  Candidate IDs: {result['candidate_ids']}")
    else:
        print(f"✗ Import failed: {response.json()}")
    
    # Verify candidates were added
    print("\n3. Verifying imported candidates...")
    response = requests.get(f"{BASE_URL}/api/elections/{election_id}/candidates")
    candidates = response.json()
    print(f"Total candidates in election: {len(candidates)}")
    for c in candidates:
        print(f"  - {c['name']} ({c['faculty']}) - External ID: {c.get('external_id', 'N/A')}")

def test_election_templates():
    """Test 6: Election templates"""
    print_header("TEST 6: ELECTION TEMPLATES")
    
    # Create a template
    print("\n1. Creating election template...")
    template_data = {
        "name": "Standard Student Election",
        "description": "Template for regular student council elections",
        "config": {
            "duration_days": 7,
            "voting_method": "IRV",
            "require_manifesto": True,
            "max_candidates": 10,
            "default_faculties": ["Engineering", "Business", "Arts", "Science", "Medicine"],
            "notification_schedule": ["start", "24h_before_end", "end"]
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/templates", json=template_data)
    if response.status_code == 200:
        result = response.json()
        template_id = result["template_id"]
        print(f"✓ Template created with ID: {template_id}")
    else:
        print(f"✗ Template creation failed: {response.json()}")
        return
    
    # Create another template
    print("\n2. Creating another template...")
    template_data2 = {
        "name": "Quick Poll Template",
        "description": "For quick decision polls",
        "config": {
            "duration_days": 1,
            "voting_method": "Simple",
            "require_manifesto": False,
            "max_candidates": 5
        }
    }
    requests.post(f"{BASE_URL}/api/templates", json=template_data2)
    
    # List all templates
    print("\n3. Listing all templates...")
    response = requests.get(f"{BASE_URL}/api/templates")
    if response.status_code == 200:
        templates = response.json()
        print(f"Found {len(templates)} templates:")
        for template in templates:
            print(f"\n  Template: {template['name']}")
            print(f"  Description: {template['description']}")
            print(f"  Created by: {template['created_by']}")
            print(f"  Config: {json.dumps(template['config'], indent=4)}")
    
    # Create election using template
    print("\n4. Creating election from template...")
    utc_now = datetime.now(timezone.utc)
    election_data = {
        "title": "Election from Template",
        "description": "Created using template",
        "start_time": utc_now.isoformat(),
        "end_time": (utc_now + timedelta(days=7)).isoformat(),
        "template_id": template_id
    }
    
    response = requests.post(f"{BASE_URL}/api/elections", json=election_data)
    if response.status_code == 200:
        print(f"✓ Election created from template: {response.json()}")
    else:
        print(f"✗ Failed: {response.json()}")

def test_vote_receipts():
    """Test 7: Vote receipt generation"""
    print_header("TEST 7: VOTE RECEIPT GENERATION")
    
    # Create election and vote
    print("\nSetting up test election...")
    election_id, votes = test_basic_election_flow()
    
    if not votes:
        print("No votes to generate receipts for!")
        return
    
    print("\n" + "-"*40)
    print("Testing receipt retrieval...")
    
    # Get receipt for first vote
    receipt_number = votes[0]['receipt_number']
    print(f"\n1. Retrieving receipt: {receipt_number}")
    
    response = requests.get(f"{BASE_URL}/api/receipts/{receipt_number}")
    if response.status_code == 200:
        print("✓ Receipt retrieved successfully")
        print("\nReceipt Preview (first 500 chars):")
        print("-"*40)
        print(response.text[:500] + "...")
    else:
        print(f"✗ Failed to retrieve receipt: {response.status_code}")
    
    # Test invalid receipt number
    print("\n2. Testing invalid receipt number...")
    response = requests.get(f"{BASE_URL}/api/receipts/INVALID-RECEIPT")
    print(f"Response: {response.status_code}")

def test_freeze_unfreeze():
    """Test 8: Election freeze/unfreeze"""
    print_header("TEST 8: ELECTION FREEZE/UNFREEZE")
    
    # Create active election
    utc_now = datetime.now(timezone.utc)
    election_data = {
        "title": "Freeze Test Election",
        "description": "Testing freeze functionality",
        "start_time": (utc_now - timedelta(hours=1)).isoformat(),
        "end_time": (utc_now + timedelta(days=1)).isoformat()
    }
    
    print("\n1. Creating active election...")
    response = requests.post(f"{BASE_URL}/api/elections", json=election_data)
    election_id = response.json()["election_id"]
    
    # Add candidates
    print("\n2. Adding candidates...")
    candidates = ["Candidate A", "Candidate B"]
    candidate_ids = []
    for name in candidates:
        response = requests.post(
            f"{BASE_URL}/api/elections/{election_id}/candidates",
            json={"name": name}
        )
        candidate_ids.append(response.json()["candidate_id"])
    
    # Try to vote normally
    print("\n3. Attempting normal vote...")
    vote_data = {
        "google_user_info": SAMPLE_GOOGLE_USERS[0],
        "election_id": election_id,
        "preferences": {
            str(candidate_ids[0]): 1,
            str(candidate_ids[1]): 2
        },
        "voter_traits": {
            "faculty": "Test",
            "gender": "Other",
            "study_level": "Undergraduate",
            "year_level": 1
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/vote", json=vote_data)
    if response.status_code == 200:
        print("✓ Vote successful before freeze")
    else:
        print(f"✗ Vote failed: {response.json()}")
    
    # Freeze election
    print("\n4. Freezing election...")
    response = requests.post(f"{BASE_URL}/api/elections/{election_id}/freeze")
    print(f"Response: {response.json()}")
    
    # Try to vote while frozen
    print("\n5. Attempting vote while frozen...")
    vote_data["google_user_info"] = SAMPLE_GOOGLE_USERS[1]  # Different user
    response = requests.post(f"{BASE_URL}/api/vote", json=vote_data)
    if response.status_code == 400:
        print(f"✓ Vote correctly blocked: {response.json()['detail']}")
    else:
        print(f"✗ Unexpected response: {response.json()}")
    
    # Unfreeze election
    print("\n6. Unfreezing election...")
    response = requests.post(f"{BASE_URL}/api/elections/{election_id}/unfreeze")
    print(f"Response: {response.json()}")
    
    # Try to vote after unfreeze
    print("\n7. Attempting vote after unfreeze...")
    response = requests.post(f"{BASE_URL}/api/vote", json=vote_data)
    if response.status_code == 200:
        print("✓ Vote successful after unfreeze")
    else:
        print(f"✗ Vote failed: {response.json()}")
    
    # Check election status
    print("\n8. Checking election status...")
    response = requests.get(f"{BASE_URL}/api/elections")
    elections = response.json()
    for e in elections:
        if e['id'] == election_id:
            print(f"Election status: {e['status']}, Frozen: {e['is_frozen']}")

def view_all_audit_logs():
    """Test 9: View all audit logs"""
    print_header("ALL AUDIT LOGS")
    
    print("\nRetrieving last 50 audit log entries...")
    response = requests.get(f"{BASE_URL}/api/audit-logs?limit=50")
    
    if response.status_code == 200:
        logs = response.json()
        print(f"\nFound {len(logs)} audit log entries:")
        
        for log in logs[:20]:  # Show first 20
            print(f"\n  [{log['timestamp']}]")
            print(f"  Action: {log['action_type']}")
            print(f"  Actor: {log.get('actor_email', 'N/A')} (ID: {log['actor_id']})")
            if log.get('election_id'):
                print(f"  Election ID: {log['election_id']}")
            if log.get('details'):
                print(f"  Details: {json.dumps(log['details'], indent=4)}")
        
        if len(logs) > 20:
            print(f"\n  ... and {len(logs) - 20} more entries")
    else:
        print(f"Failed to retrieve logs: {response.json()}")

def run_complete_test_suite():
    """Test 10: Run all tests"""
    print_header("RUNNING COMPLETE TEST SUITE")
    
    tests = [
        ("Basic Election Flow", test_basic_election_flow),
        ("Vote Verification", test_vote_verification),
        ("Audit Trail", test_audit_trail),
        ("Bulk Import JSON", test_bulk_import_json),
        ("Bulk Import CSV", test_bulk_import_csv),
        ("Election Templates", test_election_templates),
        ("Vote Receipts", test_vote_receipts),
        ("Freeze/Unfreeze", test_freeze_unfreeze)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        try:
            test_func()
            results.append((test_name, "PASSED"))
            print(f"\n✓ {test_name} completed successfully")
        except Exception as e:
            results.append((test_name, f"FAILED: {str(e)}"))
            print(f"\n✗ {test_name} failed: {str(e)}")
        
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print_header("TEST SUITE SUMMARY")
    passed = sum(1 for _, status in results if status == "PASSED")
    failed = len(results) - passed
    
    print(f"\nTotal Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    print("\nDetailed Results:")
    for test_name, status in results:
        symbol = "✓" if status == "PASSED" else "✗"
        print(f"  {symbol} {test_name}: {status}")

def main():
    """Main menu loop"""
    print("\n" + "="*60)
    print("  MONASH VOTING SYSTEM TEST SUITE")
    print("  Enhanced with Google Authentication")
    print("="*60)
    
    while True:
        print_menu()
        
        try:
            choice = input("\nEnter your choice (0-10): ").strip()
            
            if choice == "0":
                print("\nExiting test suite. Goodbye!")
                break
            elif choice == "1":
                test_basic_election_flow()
            elif choice == "2":
                test_vote_verification()
            elif choice == "3":
                test_audit_trail()
            elif choice == "4":
                test_bulk_import_json()
            elif choice == "5":
                test_bulk_import_csv()
            elif choice == "6":
                test_election_templates()
            elif choice == "7":
                test_vote_receipts()
            elif choice == "8":
                test_freeze_unfreeze()
            elif choice == "9":
                view_all_audit_logs()
            elif choice == "10":
                run_complete_test_suite()
            else:
                print("\n⚠️  Invalid choice. Please select 0-10.")
            
            if choice != "0":
                input("\n\nPress Enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()