import urllib.request
import urllib.parse
import http.cookiejar
import json
import time

base_url = "http://127.0.0.1:5000"

print("=== 1. VERIFYING SERVED HTML ===")
req = urllib.request.Request(base_url)
with urllib.request.urlopen(req) as response:
    html = response.read().decode('utf-8')

# 1. Verify Hero Section
assert "Explore Courses" in html, "Explore Courses button missing!"
assert "Become a Creator</button>" not in html or "hero-actions" not in html.split("Become a Creator")[0].split("<div class=\"hero-actions\">")[-1], "Hero button should not contain Become a Creator"

# Check hero actions directly
hero_actions_snippet = html[html.find('<div class="hero-actions">'):html.find('</div>', html.find('<div class="hero-actions">'))]
print("Hero actions block in served HTML:")
print(hero_actions_snippet.strip())
assert "Become a Creator" not in hero_actions_snippet, "Become a Creator button found in hero section!"
assert "Explore Courses" in hero_actions_snippet, "Explore Courses not in hero section!"
print(">>> Hero section verification: PASSED (Only Explore Courses button present)")

# 2. Verify Top-Right Create Account button
assert 'onclick="openRoleSelectionModal()"' in html, "Create Account button does not call openRoleSelectionModal()"
print(">>> Top-right Create Account button: PASSED (Triggers role selection modal)")

# 3. Verify Account Type / Role Selection Modal
assert 'id="authChooseRoleModal"' in html, "authChooseRoleModal missing in HTML"
assert "Create Your" in html and "Nexora Account" in html, "Modal title missing"
assert "How would you like to join Nexora?" in html, "Modal subtitle missing"
assert "Become a Creator" in html, "Become a Creator option missing"
assert "Become a Learner" in html, "Become a Learner option missing"
assert "selectRegistrationRole('creator')" in html, "Creator select handler missing"
assert "selectRegistrationRole('learner')" in html, "Learner select handler missing"
print(">>> authChooseRoleModal verification: PASSED (Contains exact required titles, options, and handlers)")

# 4. Verify Registration Modal
assert 'id="regRole"' in html, "regRole hidden input missing in authRegisterModal"
print(">>> authRegisterModal verification: PASSED (Includes regRole input)")


print("\n=== 2. VERIFYING REGISTRATION FLOWS & DATABASE PRESERVATION ===")
ts = int(time.time())

# Flow 1: Creator Registration
cj1 = http.cookiejar.CookieJar()
opener1 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj1))

creator_email = f"creator_{ts}@nexora.com"
creator_name = f"Creator User {ts}"
reg_payload_creator = {
    "full_name": creator_name,
    "email": creator_email,
    "password": "password123",
    "confirm_password": "password123",
    "role": "creator"
}

req_reg1 = urllib.request.Request(
    f"{base_url}/api/auth/register",
    data=json.dumps(reg_payload_creator).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)
with opener1.open(req_reg1) as res:
    data1 = json.loads(res.read().decode('utf-8'))
    print(f"Flow 1 Response: Status {res.status}, Message: {data1.get('message')}")
    user1 = data1.get('user', {})
    print(f"Flow 1 User: ID {user1.get('id')}, Name: '{user1.get('name')}', Role: '{user1.get('role')}'")
    assert user1.get('role') == 'creator', f"Expected role 'creator', got {user1.get('role')}"

# Verify authenticated session for creator
req_me1 = urllib.request.Request(f"{base_url}/api/auth/me")
with opener1.open(req_me1) as res:
    me_data1 = json.loads(res.read().decode('utf-8'))
    print(f"Flow 1 /api/auth/me: Role is '{me_data1.get('user', {}).get('role')}'")
    assert me_data1.get('user', {}).get('role') == 'creator', "Current authenticated session role is not creator"
print(">>> Flow 1 (Creator): PASSED & Verified!")


# Flow 2: Learner Registration
cj2 = http.cookiejar.CookieJar()
opener2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj2))

learner_email = f"learner_{ts}@nexora.com"
learner_name = f"Learner User {ts}"
reg_payload_learner = {
    "full_name": learner_name,
    "email": learner_email,
    "password": "password123",
    "confirm_password": "password123",
    "role": "learner"
}

req_reg2 = urllib.request.Request(
    f"{base_url}/api/auth/register",
    data=json.dumps(reg_payload_learner).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)
with opener2.open(req_reg2) as res:
    data2 = json.loads(res.read().decode('utf-8'))
    print(f"Flow 2 Response: Status {res.status}, Message: {data2.get('message')}")
    user2 = data2.get('user', {})
    print(f"Flow 2 User: ID {user2.get('id')}, Name: '{user2.get('name')}', Role: '{user2.get('role')}'")
    assert user2.get('role') == 'learner', f"Expected role 'learner', got {user2.get('role')}"

# Verify authenticated session for learner
req_me2 = urllib.request.Request(f"{base_url}/api/auth/me")
with opener2.open(req_me2) as res:
    me_data2 = json.loads(res.read().decode('utf-8'))
    print(f"Flow 2 /api/auth/me: Role is '{me_data2.get('user', {}).get('role')}'")
    assert me_data2.get('user', {}).get('role') == 'learner', "Current authenticated session role is not learner"
print(">>> Flow 2 (Learner): PASSED & Verified!")


print("\n=== 3. VERIFYING LOGIN PRESERVATION ===")
# Test logging in as the newly created creator
cj3 = http.cookiejar.CookieJar()
opener3 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj3))

login_req = urllib.request.Request(
    f"{base_url}/api/auth/login",
    data=json.dumps({"email": creator_email, "password": "password123"}).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)
with opener3.open(login_req) as res:
    login_data = json.loads(res.read().decode('utf-8'))
    assert login_data.get('user', {}).get('role') == 'creator', "Login did not return creator role"
    print(f"Login Creator: Role is '{login_data.get('user', {}).get('role')}' (requires_role_selection={login_data.get('requires_role_selection')})")
print(">>> Login Role Preservation: PASSED!")

print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
