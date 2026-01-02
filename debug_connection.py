import requests
import json

# === CONFIGURATION ===
FRAPPE_URL = "http://localhost:8000"
API_KEY = "fe8e26f072ee6aa"
API_SECRET = "b82f8b707e46d4c"

headers = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json"
}

def run_debug():
    print(f"--- Starting Debug for {FRAPPE_URL} ---")

    # CHECK 1: Basic Authentication
    # This checks if the API Key/Secret are even valid.
    print("\n[Step 1] Checking Authentication...")
    try:
        auth_res = requests.get(f"{FRAPPE_URL}/api/method/frappe.auth.get_logged_user", headers=headers)
        if auth_res.status_code == 200:
            print(f"✅ Success! Logged in as: {auth_res.json().get('message')}")
        else:
            print(f"❌ Auth Failed ({auth_res.status_code}): {auth_res.text}")
            return
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # CHECK 2: General Permissions
    # This checks if you can see the User list at all (without filters).
    print("\n[Step 2] Checking General User Access...")
    user_res = requests.get(f"{FRAPPE_URL}/api/resource/User?limit_page_length=3", headers=headers)
    if user_res.status_code == 200:
        users = user_res.json().get("data", [])
        print(f"✅ Success! Found {len(users)} users in the system.")
    else:
        print(f"❌ Permission Denied to User DocType: {user_res.status_code}")

    # CHECK 3: Filter Verification
    # This checks if the specific Role 'Onboarding Employee' exists and is visible.
    print("\n[Step 3] Verifying 'Onboarding Employee' Role Filter...")
    # Note: In Frappe, to filter by role, we usually check the 'Has Role' table
    role_filter = json.dumps([["Has Role", "role", "=", "Onboarding Employee"]])
    filter_url = f"{FRAPPE_URL}/api/resource/User?filters={role_filter}"
    
    filter_res = requests.get(filter_url, headers=headers)
    if filter_res.status_code == 200:
        onboarding_list = filter_res.json().get("data", [])
        print(f"✅ Filter worked! Found {len(onboarding_list)} Onboarding Employees.")
        for u in onboarding_list:
            print(f"   - Match: {u['name']}")
    else:
        print(f"❌ Filter logic error: {filter_res.text}")

if __name__ == "__main__":
    run_debug()