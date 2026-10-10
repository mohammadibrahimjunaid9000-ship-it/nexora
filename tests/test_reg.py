import urllib.request
import json
import time

ts = int(time.time())

# TEST 1: Register Creator
creator_payload = {
    'full_name': f'Test Creator {ts}',
    'email': f'creator_{ts}@test.com',
    'password': 'password123',
    'confirm_password': 'password123',
    'role': 'creator'
}
req = urllib.request.Request(
    'http://127.0.0.1:5000/api/auth/register',
    data=json.dumps(creator_payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(req)
data1 = json.loads(res.read().decode('utf-8'))
print(f"TEST 1 (Creator Register): Status {res.status}, Role stored: {data1.get('user', {}).get('role')}")
assert data1.get('user', {}).get('role') == 'creator', f"Expected creator, got {data1}"

# TEST 2: Register Learner
learner_payload = {
    'full_name': f'Test Learner {ts}',
    'email': f'learner_{ts}@test.com',
    'password': 'password123',
    'confirm_password': 'password123',
    'role': 'learner'
}
req2 = urllib.request.Request(
    'http://127.0.0.1:5000/api/auth/register',
    data=json.dumps(learner_payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
res2 = urllib.request.urlopen(req2)
data2 = json.loads(res2.read().decode('utf-8'))
print(f"TEST 2 (Learner Register): Status {res2.status}, Role stored: {data2.get('user', {}).get('role')}")
assert data2.get('user', {}).get('role') == 'learner', f"Expected learner, got {data2}"

print("All API registration tests passed successfully!")
