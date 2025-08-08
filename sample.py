import requests
import json
from datetime import datetime, timedelta, timezone

# Base URL for the API
BASE_URL = "http://localhost:8000"

print("=== Teyvat Student Council President Election - Demo ===\n")

# Get current UTC time
utc_now = datetime.now(timezone.utc)
print(f"Current UTC time: {utc_now.strftime('%Y-%m-%d %H:%M:%S')} UTC")


# 1. Create an ACTIVE election
print("1. Creating an ACTIVE election...")
election_data = {
    "title": "Teyvat Student Council President Election 2025",
    "description": "Elect the next president of the Teyvat Student Council",
    "start_time": (utc_now - timedelta(hours=2)).isoformat(),
    "end_time": (utc_now + timedelta(days=7)).isoformat()
}
print(f"Election start: {election_data['start_time']}")
print(f"Election end: {election_data['end_time']}\n")

response = requests.post(f"{BASE_URL}/api/elections", json=election_data)
print(f"Response: {response.json()}")
election_id = response.json()["election_id"]
print(f"Created election with ID: {election_id}\n")

# 2. Add Genshin-themed candidates
print("2. Adding the voting people...")
candidates = [
    {
        "name": "Nilou",
        "faculty": "Dance and Performance",
        "manifesto": "Let’s bring harmony and expression to student life through joyful festivals and dance."
    },
    {
        "name": "Raiden Shogun",
        "faculty": "Electro Engineering",
        "manifesto": "Stability through order—my rule will ensure timeless structure for our student body."
    },
    {
        "name": "Albedo",
        "faculty": "Alchemy & Science",
        "manifesto": "Curiosity is the seed of wisdom—I’ll cultivate innovation and research opportunities."
    },
    {
        "name": "Yae Miko",
        "faculty": "Literature and Publishing",
        "manifesto": "Let the student voice be heard—I will amplify creative expression and ensure our ideas flourish."
    }
]

candidate_ids = []
for candidate in candidates:
    response = requests.post(f"{BASE_URL}/api/elections/{election_id}/candidates", json=candidate)
    print(f"Added: {candidate['name']}")
    candidate_ids.append(response.json()["candidate_id"])
print()

# 3. Check election status
print("3. Checking election status...")
response = requests.get(f"{BASE_URL}/api/elections")
elections = response.json()
for election in elections:
    if election['id'] == election_id:
        print(f"Election status: {election['status']}")
        break
print()

# 4. Submit Genshin-themed votes
print("4. Submitting votes...")
sample_votes = [
    {
        "email": "lumine@monash.edu",
        "election_id": election_id,
        "preferences": {
            str(candidate_ids[0]): 1, str(candidate_ids[1]): 2,
            str(candidate_ids[2]): 3, str(candidate_ids[3]): 4
        },
        "voter_traits": {
            "faculty": "Peak",
            "gender": "Female",
            "study_level": "Undergraduate",
            "year_level": 3
        }
    },
    {
        "email": "zhongli@monash.edu",
        "election_id": election_id,
        "preferences": {
            str(candidate_ids[1]): 1, str(candidate_ids[0]): 2,
            str(candidate_ids[3]): 3, str(candidate_ids[2]): 4
        },
        "voter_traits": {
            "faculty": "poor",
            "gender": "Male",
            "study_level": "Postgraduate",
            "year_level": 1
        }
    },
    {
        "email": "kaeya@monash.edu",
        "election_id": election_id,
        "preferences": {
            str(candidate_ids[3]): 1, str(candidate_ids[2]): 2,
            str(candidate_ids[0]): 3, str(candidate_ids[1]): 4
        },
        "voter_traits": {
            "faculty": "fucking black",
            "gender": "Male",
            "study_level": "Undergraduate",
            "year_level": 2
        }
    },
    {
        "email": "collei@monash.edu",
        "election_id": election_id,
        "preferences": {
            str(candidate_ids[2]): 1, str(candidate_ids[0]): 2,
            str(candidate_ids[1]): 3, str(candidate_ids[3]): 4
        },
        "voter_traits": {
            "faculty": "shrroms",
            "gender": "Female",
            "study_level": "Undergraduate",
            "year_level": 1
        }
    },
    {
        "email": "itto@monash.edu",
        "election_id": election_id,
        "preferences": {
            str(candidate_ids[0]): 1, str(candidate_ids[3]): 2,
            str(candidate_ids[1]): 3, str(candidate_ids[2]): 4
        },
        "voter_traits": {
            "faculty": "Extracurricular niggering",
            "gender": "Male",
            "study_level": "Undergraduate",
            "year_level": 2
        }
    },
    {
        "email": "nahida@monash.edu",
        "election_id": election_id,
        "preferences": {
            str(candidate_ids[2]): 1, str(candidate_ids[1]): 2,
            str(candidate_ids[0]): 3, str(candidate_ids[3]): 4
        },
        "voter_traits": {
            "faculty": "being a child",
            "gender": "Female",
            "study_level": "Postgraduate",
            "year_level": 2
        }
    }
]

successful_votes = 0
for i, vote in enumerate(sample_votes):
    response = requests.post(f"{BASE_URL}/api/vote", json=vote)
    if response.status_code == 200:
        print(f"✓ Vote {i+1}: Success - {response.json()['confirmation_code']}")
        successful_votes += 1
    else:
        print(f"✗ Vote {i+1}: Failed - {response.json()}")

print(f"\nSuccessfully submitted {successful_votes} votes\n")

# 5. Test duplicate vote prevention
if successful_votes > 0:
    print("5. Testing duplicate vote prevention...")
    response = requests.post(f"{BASE_URL}/api/vote", json=sample_votes[0])
    print(f"Duplicate vote result: {response.status_code} - {response.json()['detail']}\n")
else:
    print("5. Skipping duplicate test (no successful votes)\n")

# 6. Retrieve and display results
print("6. Election Results\n")
response = requests.get(f"{BASE_URL}/api/elections/{election_id}/results")
results = response.json()

print(f"Election: {results['title']}")
print(f"Status: {results['status']}")
print(f"Total Votes Cast: {results['total_votes']}")

if results['total_votes'] > 0:
    print("\nFirst Preference Counts:")
    for candidate, votes in results['vote_counts'].items():
        percentage = (votes / results['total_votes']) * 100
        print(f"  {candidate}: {votes} votes ({percentage:.1f}%)")

    print("\nVoter Demographics")
    print("By Faculty:")
    for faculty, count in results['turnout_by_faculty'].items():
        print(f"  {faculty}: {count} voters")

    print("Gender")
    for gender, count in results['turnout_by_gender'].items():
        print(f"  {gender}: {count} voters")

    print("Study Level")
    for level, count in results['turnout_by_study_level'].items():
        print(f"  {level}: {count} voters")

    print("\n7. done printing vis")
    print(json.dumps({
        "election_title": results['title'],
        "vote_summary": {
            "total_votes": results['total_votes'],
            "candidate_results": results['vote_counts']
        },
        "demographic_breakdown": {
            "faculty": results['turnout_by_faculty'],
            "gender": results['turnout_by_gender'],
            "study_level": results['turnout_by_study_level']
        }
    }, indent=2))
else:
    print("failed lmfao")
